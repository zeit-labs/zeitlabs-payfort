"""Base data required for tests."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture(scope="session")
def base_data(django_db_setup, django_db_blocker):  # pylint: disable=unused-argument
    """
    Create 3 test users with fixed IDs and roles.
    Available to all tests.
    """
    with django_db_blocker.unblock():
        User.objects.all().delete()
        # User 1 - superuser + staff
        User.objects.create(
            id=1,
            username="user1",
            email="user1@example.com",
            is_superuser=True,
            is_staff=True,
        )

        # User 2 - staff only
        User.objects.create(
            id=2,
            username="user2",
            email="user2@example.com",
            is_superuser=False,
            is_staff=True,
        )

        # User 3 - regular user
        User.objects.create(
            id=3,
            username="user3",
            email="user3@example.com",
            is_superuser=False,
            is_staff=False,
        )
