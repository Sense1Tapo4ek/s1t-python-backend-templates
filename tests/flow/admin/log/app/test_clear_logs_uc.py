"""Flow test for ClearLogsUc — destructive op delegating to ILogPurger."""

from unittest.mock import AsyncMock

import pytest

from admin.log.app.use_cases import ClearLogsUc


@pytest.mark.asyncio
class TestClearLogsUc:
    async def test_returns_deleted_count_from_purger(self) -> None:
        purger = AsyncMock()
        purger.purge_all.return_value = 42
        uc = ClearLogsUc(_purger=purger)

        result = await uc()

        assert result == 42
        purger.purge_all.assert_awaited_once_with()

    async def test_no_extra_calls_on_empty_table(self) -> None:
        purger = AsyncMock()
        purger.purge_all.return_value = 0
        uc = ClearLogsUc(_purger=purger)

        result = await uc()

        assert result == 0
        purger.purge_all.assert_awaited_once_with()

    async def test_propagates_purger_failure(self) -> None:
        purger = AsyncMock()
        purger.purge_all.side_effect = RuntimeError("disk full")
        uc = ClearLogsUc(_purger=purger)

        with pytest.raises(RuntimeError, match="disk full"):
            await uc()
