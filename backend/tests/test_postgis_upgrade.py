from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.sites.management.commands.upgrade_postgis import Command

MODULE = "apps.sites.management.commands.upgrade_postgis"


def exercise(inventories):
    cursor = MagicMock()
    cursor.fetchall.side_effect = inventories
    database = MagicMock(vendor="postgresql")
    database.cursor.return_value.__enter__.return_value = cursor
    output = StringIO()
    command = Command(stdout=output)
    with (
        override_settings(ENABLE_GIS=True),
        patch(f"{MODULE}.connection", database),
        patch(f"{MODULE}.transaction.atomic"),
    ):
        command.handle()
    return cursor, output.getvalue()


@override_settings(ENABLE_GIS=False)
def test_non_gis_database_does_not_attempt_extension_changes():
    output = StringIO()
    with patch(f"{MODULE}.connection") as database:
        call_command("upgrade_postgis", stdout=output)
    database.cursor.assert_not_called()
    assert "skipped" in output.getvalue()


def test_existing_35_extensions_upgrade_together():
    cursor, output = exercise(
        [
            [("postgis", "3.5.5", "3.6.4"), ("postgis_topology", "3.5.5", "3.6.4")],
            [("postgis", "3.6.4", "3.6.4"), ("postgis_topology", "3.6.4", "3.6.4")],
        ]
    )
    assert any(
        call.args[0] == "SELECT postgis_extensions_upgrade()"
        for call in cursor.execute.call_args_list
    )
    assert "upgraded and verified" in output


def test_current_extensions_do_not_repeat_upgrade():
    cursor, output = exercise([[("postgis", "3.6.4", "3.6.4")]])
    assert not any(
        call.args[0] == "SELECT postgis_extensions_upgrade()"
        for call in cursor.execute.call_args_list
    )
    assert "already current" in output


@pytest.mark.parametrize(
    "inventory",
    [
        [],
        [("postgis", "3.5.5", "3.7.0")],
        [("postgis", "3.5.5", None)],
        [("postgis", "3.4.4", "3.6.4")],
        [("postgis", "3.5.5", "3.6.5dev")],
    ],
)
def test_unreviewed_or_missing_versions_fail_before_upgrade(inventory):
    with pytest.raises(CommandError):
        exercise([inventory])


@pytest.mark.parametrize(
    "after",
    [
        [("postgis", "3.5.5", "3.6.4")],
        [("postgis", "3.6.4", "3.6.4"), ("postgis_topology", "3.6.4", "3.6.4")],
    ],
)
def test_incomplete_or_unexpected_upgrade_fails(after):
    with pytest.raises(CommandError):
        exercise([[("postgis", "3.5.5", "3.6.4")], after])
