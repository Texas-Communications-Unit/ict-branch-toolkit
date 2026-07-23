import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, UserRoleAssignment


class Command(BaseCommand):
    help = "Create the configured local development administrator when absent."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.invalid")
        if not username or not password:
            raise CommandError(
                "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD are required"
            )
        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            user = user_model.objects.get(username=username)
            UserRoleAssignment.objects.get_or_create(
                user=user, defaults={"role": Role.ADMINISTRATOR}
            )
            self.stdout.write("Development administrator already exists.")
            return
        user = user_model.objects.create_superuser(
            username=username, email=email, password=password
        )
        UserRoleAssignment.objects.create(user=user, role=Role.ADMINISTRATOR, assigned_by=user)
        self.stdout.write(self.style.SUCCESS("Development administrator created."))
