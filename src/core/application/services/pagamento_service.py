from typing import List
from src.core.application.interfaces.pagamento import IPagamentoService
from src.core.domain.aggregates.pagamento_aggregate import PagamentoAggregate
from src.core.domain.aggregates.pedido_aggregate import PedidoAggregate
from src.core.domain.entities.meio_de_pagamento_entity import MeioDePagamentoEntity
from src.core.domain.entities.pagamento_entity import PartialPagamentoEntity
from src.core.helpers.enums.compra_status import CompraStatus
from src.core.helpers.enums.pagamento_status import PagamentoStatus


class PagamentoService(IPagamentoService):
    def initiate_purchase_payment(
        self, pedido_id: int, payment_method_id: int, webhook_url: str
    ) -> PagamentoAggregate:
        pedido = self.purchase_query.get(pedido_id)
        if not pedido:
            raise ValueError("Pedido não encontrado.")
        if pedido.payments:
            raise ValueError("Pedido já foi pago.")
        if pedido.purchase.total.value <= 0:
            raise ValueError("Valor do pedido não pode ser zero ou negativo")
        if pedido.purchase.status != CompraStatus.CRIANDO:
            raise ValueError("Pedido inválido para pagamento.")
        payment_method = self.meio_de_pagamento_query.get(payment_method_id)
        if not payment_method:
            raise ValueError("Meio de pagamento não encontrado.")
        if payment_method.is_active is False:
            raise ValueError("Meio de pagamento inativo.")
        if self.payment_provider.initiate_payment(pedido.purchase):
            payment_entity = PartialPagamentoEntity(
                payment_method=payment_method,
                status=PagamentoStatus.PROCESSANDO,
                payment_value=pedido.purchase.total,
                webhook_url=webhook_url,
            )
            payment: PagamentoAggregate = self.payment_repository.create(
                payment_entity, pedido.purchase
            )
            pedido.purchase.status = CompraStatus.CONCLUINDO
            payment.purchase = self.pedido_repository.update(pedido.purchase)
            return payment
        raise ValueError("Falha ao processar pagamento.")

    def cancel_purchase_payment(self, payment_id: int) -> PedidoAggregate:
        payment = self.payment_repository.get(payment_id)
        if not payment:
            raise ValueError("Pagamento não encontrado.")

        if payment.payment.status == PagamentoStatus.PAGO:
            raise ValueError("Pagamento já concluído.")

        if payment.payment.status not in (
            PagamentoStatus.PROCESSANDO,
            PagamentoStatus.PENDENTE,
        ):
            raise ValueError("Pagamento não está ativo.")

        if not payment.purchase:
            raise ValueError("Nenhum pedido associado ao pagamento encontrado.")

        if self.payment_provider.cancel_payment(payment.payment):
            payment.payment.status = PagamentoStatus.CANCELADO
            payment.payment = self.payment_repository.update(payment.payment)
            payment.purchase.status = CompraStatus.CRIANDO
            payment.purchase = self.pedido_repository.update(payment.purchase)
        else:
            raise ValueError("Falha ao cancelar pagamento.")
        return payment

    def finalize_purchase_payment(self, payment_id: int) -> PagamentoAggregate:
        payment = self.payment_repository.get(payment_id)
        if not payment:
            raise ValueError("Pagamento não encontrado.")

        if payment.payment.status == PagamentoStatus.PAGO:
            raise ValueError("Pagamento já concluído.")

        if payment.payment.status not in (
            PagamentoStatus.PROCESSANDO,
            PagamentoStatus.PENDENTE,
        ):
            raise ValueError("Pagamento não está ativo.")

        if not payment.purchase:
            raise ValueError("Nenhum pedido associado ao pagamento encontrado.")

        if self.payment_provider.finalize_payment(payment.payment):
            payment.payment.status = PagamentoStatus.PAGO
            payment.payment = self.payment_repository.update(payment.payment)
            payment.purchase.status = CompraStatus.CONCLUIDO
            payment.purchase = self.pedido_repository.update(payment.purchase)
        else:
            raise ValueError("Falha ao finalizar o pagamento.")
        return payment

    def list_payment_methods(self) -> List[MeioDePagamentoEntity]:
        return self.meio_de_pagamento_query.get_all()

    def get_payment_method(
        self, payment_method_id: int
    ) -> MeioDePagamentoEntity | None:
        return self.meio_de_pagamento_query.get(payment_method_id)

    def get_payment(self, payment_id: int) -> PagamentoAggregate | None:
        return self.payment_repository.get(payment_id)
