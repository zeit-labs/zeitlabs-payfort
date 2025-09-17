"""Test views for the zeitlabs_payment payfort provider"""
import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from zeitlabs_payments.exceptions import CartFulfillmentError, DuplicateTransactionError, GatewayError, InvalidCartError
from zeitlabs_payments.models import AuditLog, Cart, CatalogueItem, Invoice, Transaction

from payfort.views import PayFortBaseView, PayfortFeedbackView

User = get_user_model()


@pytest.mark.django_db
class TestPayFortBaseViewWithMocks:
    """PayFortBaseView tests with mocked payment processor."""

    factory = RequestFactory()
    view = PayFortBaseView()
    site = cart = None

    def setup_method(self):
        """setup"""
        self.site = Site.objects.create(name='MockSite', domain='mocksite.com')
        self.cart = Cart.objects.create(
            user=User.objects.get(id=3),
            status=Cart.Status.PROCESSING
        )

    @patch("payfort.processor.PayFort.get_cart")
    def test_cart_returns_mocked_cart(self, mock_get_cart):
        """Return a mocked Cart object via get_cart()."""
        mock_get_cart.return_value = self.cart
        merchant_ref = f"{self.site.id}-{self.cart.id}"
        request = self.factory.post("/fake-url/", data={"merchant_reference": merchant_ref})
        self.view.request = request

        cart = self.view.cart
        assert cart == self.cart
        mock_get_cart.assert_called_once_with(str(self.cart.id))

    @patch("payfort.processor.PayFort.get_cart")
    def test_cart_returns_none_on_invalidcart_error(self, mock_get_cart):
        """Return None if get_cart() raises InvalidCartError."""
        mock_get_cart.side_effect = InvalidCartError("Invalid cart")
        merchant_ref = f"{self.site.id}-999"
        request = self.factory.post("/fake-url/", data={"merchant_reference": merchant_ref})
        self.view.request = request

        cart = self.view.cart
        assert cart is None
        mock_get_cart.assert_called_once()

    @patch("payfort.processor.PayFort.get_site")
    def test_site_returns_mocked_site(self, mock_get_site):
        """Return a mocked Site object via get_site()."""
        mock_get_site.return_value = self.site
        merchant_ref = f"{self.site.id}-{self.cart.id}"
        request = self.factory.post("/fake-url/", data={"merchant_reference": merchant_ref})
        self.view.request = request

        site = self.view.site
        assert site == self.site
        mock_get_site.assert_called_once_with(str(self.site.id))

    @patch("payfort.processor.PayFort.get_site")
    def test_site_returns_none_on_gateway_error(self, mock_get_site):
        """Return None if get_site() raises GatewayError."""
        mock_get_site.side_effect = GatewayError("Invalid site")
        merchant_ref = f"999-{self.cart.id}"
        request = self.factory.post("/fake-url/", data={"merchant_reference": merchant_ref})
        self.view.request = request

        site = self.view.site
        assert site is None
        mock_get_site.assert_called_once()

    def test_cart_returns_none_if_request_missing(self):
        self.view.request = None
        assert self.view.cart is None

    def test_site_returns_none_if_request_missing(self):
        self.view.request = None
        assert self.view.site is None

    def test_cart_returns_none_if_merchant_reference_missing(self):
        request = self.factory.post('/fake-url/', data={})
        self.view.request = request
        assert self.view.cart is None

    def test_site_returns_none_if_merchant_reference_missing(self):
        request = self.factory.post('/fake-url/', data={})
        self.view.request = request
        assert self.view.site is None


@pytest.mark.usefixtures('base_data')
class PayfortFeedbackTestView(TestCase):
    """Payfort feedback test case."""

    def setUp(self) -> None:
        """
        Set up test data for the Payfort feedback tests.

        :return: None
        """
        self.user = User.objects.get(id=3)
        self.cart = Cart.objects.create(user=self.user, status=Cart.Status.PROCESSING)
        self.course_item = CatalogueItem.objects.create(sku='custom-sku-1', price='45', currency='USD')
        self.cart.items.create(
            catalogue_item=self.course_item,
            original_price=self.course_item.price,
            final_price=self.course_item.price,
        )
        self.site = Site.objects.create(name='test.com', domain='test.com')
        self.provider = 'payfort'
        self.url = reverse('payfort:return')

        self.valid_response = {
            'amount': '150',
            'response_code': '14000',
            'acquirer_response_message': 'Success',
            'card_number': '411111******1111',
            'card_holder_name': 'Tehreem',
            'signature': '141ae3d36be4f7f50cefbb966b26c8ee073a84dd32d99eec3084d19efb247895',
            'merchant_identifier': 'abcdi',
            'access_code': 'm6ScifP9737ykbx31Z7i',
            'order_description': 'some order description',
            'payment_option': 'VISA',
            'expiry_date': '2511',
            'customer_ip': '101.53.219.17',
            'language': 'en',
            'eci': 'ECOMMERCE',
            'fort_id': '169996200024611493',
            'command': 'PURCHASE',
            'response_message': 'Success',
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'authorization_code': '742138',
            'customer_email': 'tehreemsadat19@gmail.com',
            'currency': 'USD',
            'acquirer_response_code': '00',
            'status': '14',
        }
        self.request_factory = RequestFactory()

    @patch("payfort.processor.PayFort.get_cart")
    def test_post_for_invalid_cart_in_merchant_ref(self, mock_get_cart) -> None:
        """
        Test that posting with an invalid cart ID in merchant_reference raises PayFortException.

        :return: None
        """
        mock_get_cart.side_effect = InvalidCartError("Invalid cart")
        data = self.valid_response.copy()
        data.update({'merchant_reference': '1-10000'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        response = PayfortFeedbackView.as_view()(request)
        assert response.status_code == 400

    @patch("payfort.processor.PayFort.get_site")
    def test_post_for_invalid_site_in_merchant_ref(self, mock_get_site) -> None:
        """
        Test that posting with an invalid site ID in merchant_reference raises PayFortException.

        :return: None
        """
        mock_get_site.side_effect = GatewayError("Invalid site")
        data = self.valid_response.copy()
        data.update({'merchant_reference': f'10000-{self.cart.id}'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        response = PayfortFeedbackView.as_view()(request)
        assert response.status_code == 400

    def test_post_for_invalid_signature(self) -> None:
        """
        Test post request with an invalid signature.

        :return: None
        """
        data = self.valid_response.copy()
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        assert not AuditLog.objects.filter(
            action=AuditLog.AuditActions.BAD_RESPONSE_SIGNATURE,
            cart=self.cart,
            gateway='payfort'
        ).exists(), 'AuditLog for BAD_RESPONSE_SIGNATURE with PayFort gateway should not existbefore fucntion call.'

        response = PayfortFeedbackView.as_view()(request)
        assert response.status_code == 400
        assert AuditLog.objects.filter(
            action=AuditLog.AuditActions.BAD_RESPONSE_SIGNATURE,
            cart=self.cart,
            gateway='payfort'
        ).exists(), 'AuditLog for BAD_RESPONSE_SIGNATURE with PayFort gateway and the given cart should exist'

    @pytest.mark.django_db
    @patch('payfort.views.verify_signature')
    def test_post_for_cart_not_in_processing_state(
        self, mock_verify_signature  # pylint: disable=unused-argument
    ) -> None:
        """
        Test that posting with a cart not in PROCESSING state raises PayFortException.

        :return: None
        """
        self.cart.status = Cart.Status.PENDING
        self.cart.save()
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        assert not AuditLog.objects.filter(
            gateway='payfort',
            action=AuditLog.AuditActions.RESPONSE_INVALID_CART,
        ).exists()
        response = PayfortFeedbackView.as_view()(request)
        assert AuditLog.objects.filter(gateway='payfort', action=AuditLog.AuditActions.RESPONSE_INVALID_CART).exists()
        assert response.status_code == 200

    @patch('payfort.views.logger')
    @patch('payfort.views.verify_signature')
    def test_post_for_unsuccessful_payment(
        self, mock_verify_signature, mock_logger  # pylint: disable=unused-argument
    ) -> None:
        """
        Test handling of unsuccessful payment status.

        :param mock_render: mocked render function
        :return: None
        """
        data = self.valid_response.copy()
        data.update({'status': '20'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        response = PayfortFeedbackView.as_view()(request)
        mock_logger.warning.assert_called_with(
            f'PayFort payment unsuccessful. Status: 20, Data: {data}'
        )
        assert response.status_code == 200

    @patch('payfort.views.logger.error')
    @patch('payfort.views.verify_signature')
    @patch("payfort.processor.PayFort.fulfill_cart")
    def test_post_success_for_cart_fullfillment_error(
        self, mock_fulfill_cart, mock_verify_signature, mock_logger  # pylint: disable=unused-argument
    ) -> None:
        """
        Test successful payment but error on cart fullfillment, triggers error logging and error page.

        :param mock_logger: mocked logger.error function
        :param mock_render: mocked render function
        :return: None
        """
        mock_fulfill_cart.side_effect = CartFulfillmentError("Invalid cart")
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        response = PayfortFeedbackView.as_view()(request)
        mock_logger.assert_called_with(
            'Failed to fulfill cart 1 or to create invoice: Invalid cart'
        )
        assert response.status_code == 200

    @patch('payfort.views.logger.error')
    @patch('payfort.views.verify_signature')
    @patch("payfort.processor.PayFort.handle_payment")
    def test_post_success_for_rolled_back_of_tables_on_handle_payment_error(
        self, mock_handle_payment, mock_verify_signature, mock_logger  # pylint: disable=unused-argument
    ) -> None:
        """
        Test pst request for handle payment generic exception.

        :param mock_logger: mocked logger.error function
        :param mock_render: mocked render function
        :return: None
        """
        mock_handle_payment.side_effect = Exception("Unknown exception")

        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user

        response = PayfortFeedbackView.as_view()(request)
        mock_logger.assert_called_with(
            'Payment transaction failed and rolled back for cart 1: Unknown exception'
        )
        assert response.status_code == 200

    @patch('payfort.views.AuditLog.log')
    @patch('payfort.views.verify_signature')
    @patch("payfort.processor.PayFort.handle_payment")
    def test_post_success_for_duplicate_transaction(
        self, mock_handle_payment, mock_verify_signature, mock_audit_log  # pylint: disable=unused-argument
    ) -> None:
        """
        Test pst request for handle payment generic exception.

        :param mock_logger: mocked logger.error function
        :param mock_render: mocked render function
        :return: None
        """
        mock_handle_payment.side_effect = DuplicateTransactionError('Transaction already exist.')
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user

        response = PayfortFeedbackView.as_view()(request)
        mock_audit_log.assert_called_with(
            action=AuditLog.AuditActions.DUPLICATE_TRANSACTION,
            cart=self.cart,
            gateway='payfort',
            context={
                'transaction_id': self.valid_response['fort_id'],
                'cart_status': self.cart.status
            }
        )
        assert response.status_code == 200

    @patch('payfort.views.verify_signature')
    @patch("payfort.processor.PayFort.fulfill_cart")
    @patch("payfort.processor.PayFort.handle_payment")
    def test_post_for_successful_payment(
        self, mock_handle_payment, mock_fulfill_cart, mock_verify_signature  # pylint: disable=unused-argument
    ) -> None:
        """
        Test the full successful payment flow and enrollment.

        :param mock_render: mocked render function
        :return: None
        """
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        response = PayfortFeedbackView.as_view()(request)
        mock_handle_payment.assert_called_with(
            cart=self.cart,
            user=request.user if request.user.is_authenticated else None,
            transaction_status=self.valid_response['response_message'],
            transaction_id=self.valid_response['fort_id'],
            method=self.valid_response['payment_option'],
            amount=self.valid_response['amount'],
            currency=self.valid_response['currency'],
            reason=self.valid_response['acquirer_response_message'],
            response=self.valid_response
        )
        mock_fulfill_cart.assert_called_with(self.cart)
        assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('base_data')
class PayFortStatusViewTest(APITestCase):
    """Tests for PayFortStatusView"""

    def setUp(self):
        """Setup"""
        self.user = User.objects.get(id=3)
        self.cart = Cart.objects.create(user=self.user, status=Cart.Status.PROCESSING)
        self.course_item = CatalogueItem.objects.create(sku='custom-sku-1', price='45', currency='USD')
        self.cart.items.create(
            catalogue_item=self.course_item,
            original_price=self.course_item.price,
            final_price=self.course_item.price,
        )
        self.site = Site.objects.create(name='test.com', domain='test.com')
        self.url = reverse('payfort:status')

    def login_user(self, user):
        """Helper to login user"""
        self.client.force_login(user)

    def test_unauthorized(self):
        """Verify that the view returns 404 when the user is not authenticated"""
        response = self.client.get(self.url, data={})
        self.assertEqual(response.status_code, 400)

    @patch("payfort.processor.PayFort.get_cart")
    def test_get_failed_for_invalid_merchant_ref(self, mock_get_cart):
        """Cart could not be found"""
        mock_get_cart.side_effect = InvalidCartError("Invalid cart")
        self.login_user(self.user)
        response = self.client.get(self.url, data={
            'merchant_reference': '1111-2222',
            'transaction_id': '1234'
        })
        assert response.status_code == 404
        assert response.json()['error'] == 'merchant_reference: 1111-2222 is invalid. Unable to retrieve cart.'

    def test_get_failed_for_missing_merchant_ref(self):
        """Missing merchant reference"""
        self.login_user(self.user)
        response = self.client.get(self.url, data={'transaction_id': '1234'})
        assert response.status_code == 400
        assert response.json()['error'] == 'Merchant Reference is required to verify payment status.'

    def test_get_failed_for_missing_transaction_id(self):
        """Missing transaction_id"""
        self.login_user(self.user)
        response = self.client.get(self.url, data={'merchant_reference': '1-1'})
        assert response.status_code == 400
        assert response.json()['error'] == 'Transaction Id is required to verify payment status.'

    @patch("payfort.views.reverse")
    def test_paid_cart_with_invoice(self, mock_reverse):
        """Cart is PAID and invoice exists"""
        self.login_user(self.user)
        self.cart.status = Cart.Status.PAID
        self.cart.save()

        mock_reverse.return_value = '/fake/invoice_url/'
        transaction = Transaction.objects.create(
            gateway_transaction_id='tx123',
            gateway='payfort',
            amount=self.course_item.price,
        )

        Invoice.objects.create(
            cart=self.cart,
            status=Invoice.InvoiceStatus.PAID,
            invoice_number='DEV-100',
            related_transaction=transaction,
            total=self.course_item.price,
            gross_total=self.course_item.price,
        )

        response = self.client.get(self.url, data={
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'transaction_id': 'tx123'
        })
        assert response.status_code == 200
        data = response.json()
        assert data['invoice'] == 'DEV-100'
        assert data['invoice_url']

    def test_paid_cart_without_invoice(self):
        """Cart is PAID but no invoice found"""
        self.login_user(self.user)
        self.cart.status = Cart.Status.PAID
        self.cart.save()

        response = self.client.get(self.url, data={
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'transaction_id': 'does-npt-matter'
        })
        assert response.status_code == 204

    def test_processing_cart(self):
        """Cart in PROCESSING status"""
        self.login_user(self.user)
        response = self.client.get(self.url, data={
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'transaction_id': 'does-npt-matter'
        })
        assert response.status_code == 204

    def test_unknown_cart_status(self):
        """Cart in unknown status"""
        self.login_user(self.user)
        self.cart.status = 'UNKNOWN'
        self.cart.save()
        response = self.client.get(self.url, data={
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'transaction_id': 'does-not-matter'
        })
        assert response.status_code == 404
        data = response.json()
        assert data['error'] == f'cart is in status: {self.cart.status}.'


class PayFortReturnViewTest(TestCase):
    """PayFortReturnView Tests."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.get(id=3)
        self.cart = Cart.objects.create(user=self.user, status=Cart.Status.PROCESSING)
        self.course_item = CatalogueItem.objects.create(sku='custom-sku-1', price='45', currency='USD')
        self.cart.items.create(
            catalogue_item=self.course_item,
            original_price=self.course_item.price,
            final_price=self.course_item.price,
        )
        self.site = Site.objects.create(name='test.com', domain='test.com')
        self.client = Client()

    @patch("payfort.views.AuditLog.log")
    def test_missing_signature(self, mock_audit_log):
        data = {
            'other': '1234',
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
        }
        response = self.client.post(reverse('payfort:return'), data)
        assert response.status_code == 200
        mock_audit_log.assert_called_with(
            action=AuditLog.AuditActions.BAD_RESPONSE_SIGNATURE,
            cart=self.cart,
            gateway='payfort',
            context={'data': data}
        )
        self.assertTemplateUsed(response, 'zeitlabs_payments/payment_error.html')

    @patch("payfort.views.AuditLog.log")
    def test_bad_signature_renders_error_page(self, mock_audit_log):
        data = {
            'other': '1234',
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'signature': 'invalid'
        }
        response = self.client.post(reverse('payfort:return'), data)
        assert response.status_code == 200
        mock_audit_log.assert_called_with(
            action=AuditLog.AuditActions.BAD_RESPONSE_SIGNATURE,
            cart=self.cart,
            gateway='payfort',
            context={'data': data}
        )
        self.assertTemplateUsed(response, 'zeitlabs_payments/payment_error.html')

    @patch('payfort.views.logger.error')
    def test_missing_merchant_identifier(self, mock_error_log):
        data = {'other': '1234'}

        params_copy = data.copy()
        sorted_keys = sorted(params_copy, key=lambda arg: arg.lower())
        sorted_dict = {key: params_copy[key] for key in sorted_keys}
        result_string = (
            f"test-response-phrase{''.join(f'{key}={value}' for key, value in sorted_dict.items())}"
            'test-response-phrase'
        )
        expected_signature = hashlib.sha256(result_string.encode()).hexdigest()

        data.update({'signature': expected_signature})
        response = self.client.post(reverse('payfort:return'), data)
        mock_error_log.assert_called_with(
            'Payfort payment failed! with merchant_reference: None, status: None and response_code: None'
        )
        self.assertTemplateUsed(response, 'zeitlabs_payments/payment_error.html')

    @patch('payfort.views.logger.error')
    def test_post_for_failed_status(self, mock_error_log):
        data = {
            'other': '1234',
            'status': 'not-success',
            'response_code': 11
        }

        params_copy = data.copy()
        sorted_keys = sorted(params_copy, key=lambda arg: arg.lower())
        sorted_dict = {key: params_copy[key] for key in sorted_keys}
        result_string = (
            f"test-response-phrase{''.join(f'{key}={value}' for key, value in sorted_dict.items())}"
            'test-response-phrase'
        )
        expected_signature = hashlib.sha256(result_string.encode()).hexdigest()

        data.update({'signature': expected_signature})
        response = self.client.post(reverse('payfort:return'), data)
        mock_error_log.assert_called_with(
            'Payfort payment failed! with merchant_reference: None, status: not-success and response_code: 11'
        )
        self.assertTemplateUsed(response, 'zeitlabs_payments/payment_error.html')

    def test_post_for_verify_format_failiure(self):
        data = {
            'other': '1234',
            'status': '14',
            'response_code': 14
        }

        params_copy = data.copy()
        sorted_keys = sorted(params_copy, key=lambda arg: arg.lower())
        sorted_dict = {key: params_copy[key] for key in sorted_keys}
        result_string = (
            f"test-response-phrase{''.join(f'{key}={value}' for key, value in sorted_dict.items())}"
            'test-response-phrase'
        )
        expected_signature = hashlib.sha256(result_string.encode()).hexdigest()

        data.update({'signature': expected_signature})
        response = self.client.post(reverse('payfort:return'), data)
        self.assertTemplateUsed(response, 'zeitlabs_payments/payment_error.html')

    def test_post_success(self):
        def fake_reverse(name, args=None, kwargs=None):
            if name.endswith("payment-error"):
                return f"/fake/error/{args[0]}"
            if name.endswith("payment-success"):
                return f"/fake/success/{args[0]}"
            return f"/fake/{name}"
        data = {
            'amount': '150',
            'response_code': '14000',
            'merchant_identifier': 'abcdi',
            'fort_id': '123456',
            'command': 'PURCHASE',
            'response_message': 'Success',
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'currency': 'USD',
            'status': '14',
            'eci': 'test'
        }

        params_copy = data.copy()
        sorted_keys = sorted(params_copy, key=lambda arg: arg.lower())
        sorted_dict = {key: params_copy[key] for key in sorted_keys}
        result_string = (
            f"test-response-phrase{''.join(f'{key}={value}' for key, value in sorted_dict.items())}"
            'test-response-phrase'
        )
        expected_signature = hashlib.sha256(result_string.encode()).hexdigest()

        data.update({'signature': expected_signature})

        with patch("payfort.views.reverse", side_effect=fake_reverse):
            response = self.client.post(reverse('payfort:return'), data)
            self.assertTemplateUsed(response, 'zeitlabs_payments/wait_feedback.html')
            assert response.context['ecommerce_transaction_id'] == '123456'
            assert response.context['ecommerce_status_url'] == '/fake/payfort:status'
            assert response.context['ecommerce_error_url'] == '/fake/error/123456'
            assert response.context['ecommerce_success_url'] == '/fake/success/123456'
            assert response.context['ecommerce_max_attempts'] == 24
            assert response.context['ecommerce_wait_time'] == 5000
            for key, value in data.items():
                assert response.context[key] == value
