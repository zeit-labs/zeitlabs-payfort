"""Zeitlabs payments models mocks for testing purposes."""

from django.contrib.auth import get_user_model
from django.db import models


class Cart(models.Model):
    """Cart model."""

    class Status(models.TextChoices):
        """Cart states."""
        PENDING = 'pending'
        PROCESSING = 'processing'
        PAID = 'paid'

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='carts')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_cart'

    @property
    def total(self) -> int:
        """Calculate total."""
        return sum(item.final_price for item in self.items.all())

    @property
    def discount_total(self) -> int:
        """Calculate discount total."""
        return sum(item.discount_amount for item in self.items.all())

    @property
    def tax_total(self) -> int:
        """Calculate tax total."""
        return sum(item.tax_amount for item in self.items.all())

    @property
    def gross_total(self) -> int:
        """Calculate raw total before appling any discount and tax."""
        return sum(item.original_price for item in self.items.all())


class CatalogueItem(models.Model):
    """CatalogueItem model."""

    class ItemType(models.TextChoices):
        """Catalogue Item Types."""
        PAID_COURSE = 'paid_course'

    sku = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ItemType.choices)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, blank=True, null=True)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_catalogueitem'


class CartItem(models.Model):
    """CartItem model."""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    catalogue_item = models.ForeignKey(CatalogueItem, on_delete=models.PROTECT)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_cartitem'


class AuditLog(models.Model):
    """AuditLog model."""

    class AuditActions:
        """Audit log actions."""
        CART_FULFILLMENT_ERROR = 'cart_fulfillment_error'
        USER_ENROLLED = 'user_enrolled'
        USER_ENROLLED_ERROR = 'user_enrolled_error'
        REDIRECT_TO_PAYMENT = 'redirect_to_payment_gateway'
        DUPLICATE_TRANSACTION = 'duplicate_transaction_detected'
        BAD_RESPONSE_SIGNATURE = 'bad_response_signature'
        RECEIVED_RESPONSE = 'received_gateway_response'
        RESPONSE_INVALID_CART = 'response_for_invalid_cart'
        TRANSACTION_ROLLED_BACK = 'transaction_rolled_back'
        CART_STATUS_UPDATED = 'cart_status_updated'
        CART_FULFILLED = 'cart_fulfilled'

    action = models.CharField(max_length=32)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='audits', null=True)
    gateway = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_auditlog'

    @classmethod
    def log(cls, action, context=None, cart=None, gateway=None):  # pylint: disable=unused-argument
        """Mock"""
        AuditLog.objects.create(action=action, cart=cart, gateway=gateway)


class Transaction(models.Model):
    """Transaction model."""

    class TransactionType(models.TextChoices):
        """Transaction types."""
        PAYMENT = 'payment'
        REFUND = 'refund'

    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, related_name='transactions', null=True)
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=50)
    gateway = models.CharField(max_length=50)
    gateway_transaction_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_transaction'


class Invoice(models.Model):
    """Invoice model."""

    class InvoiceStatus(models.TextChoices):
        """Invoice statuses."""
        DRAFT = 'draft'
        PAID = 'paid'

    invoice_number = models.CharField(max_length=255, unique=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='invoices')
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    gross_total = models.DecimalField(max_digits=10, decimal_places=2)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    related_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'fake_models'
        db_table = 'zeitlabs_payments_invoice'
