"""Mock."""

from unittest.mock import MagicMock

from django.contrib.sites.models import Site
from zeitlabs_payments.models import Cart


class BaseProcessor:
    """Base class for all payment processors."""

    SLUG: str
    NAME: str
    CHECKOUT_TEXT: str
    PAYMENT_INITIALIZATION_URL: str

    @classmethod
    def get_payment_method_metadata(cls, cart):
        """MOCK"""
        return {
            'slug': cls.SLUG,
            'title': cls.NAME,
            'checkout_text': cls.CHECKOUT_TEXT,
            'url': f'http://test.com/payment/{cls.SLUG}/{cart.id}'
        }

    def get_transaction_parameters_base(self, cart, request):
        """MOCK"""
        return {
            'language': 'en',
            'order_reference': f'{request.site.id}-{cart.id}',
            'amount': int(cart.total),
            'currency': 'USD',
            'user_email': cart.user.email,
            'order_description': 'some description',
        }

    def get_cart(self, cart_id):
        """MOCK"""
        return Cart.objects.get(id=cart_id)

    def get_site(self, site_id):
        """MOCK"""
        return Site.objects.get(id=site_id)

    def handle_payment(  # pylint: disable= too-many-positional-arguments, unused-argument
        self,
        cart,
        user,
        transaction_status,
        transaction_id,
        method,
        amount,
        currency,
        reason,
        response=None,
        record_webhook_event=True,
    ):
        """MOCK"""
        return MagicMock()

    def create_invoice(self, cart, request, transaction_record=None):  # pylint: disable=unused-argument
        """MOCK"""
        return MagicMock()

    def fulfill_cart(self, cart):  # pylint: disable=unused-argument
        """MOCK"""
        return
