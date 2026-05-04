from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.enums import NUMERIC_METRICS
from app.domain.repositories import EntryRepository


class AnalysisService:
    """Builds pandas DataFrames over the user's logged data.

    Operates on already-aggregated rows from the repository (avg per metric/day),
    so no decryption is needed and free-text columns never leave the DB.
    """

    def __init__(self, repo: EntryRepository) -> None:
        self._repo = repo

    async def daily_summary(self, user_id: int, start: date, end: date) -> pd.DataFrame:
        """Returns a DataFrame indexed by date with one column per numeric metric.

        Columns hold the daily average. Rows for missing days are not filled —
        callers can `.reindex(pd.date_range(...))` if continuous index is needed.
        """
        rows = await self._repo.daily_aggregates(user_id, start, end)
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            rows, columns=["entry_date", "metric_type", "avg_numeric", "count"]
        )
        numeric_names = {m.value for m in NUMERIC_METRICS}
        df = df[df["metric_type"].isin(numeric_names)]
        if df.empty:
            return pd.DataFrame()

        df["avg_numeric"] = df["avg_numeric"].astype(float)
        wide = df.pivot_table(
            index="entry_date",
            columns="metric_type",
            values="avg_numeric",
            aggfunc="mean",
        )
        wide.index = pd.to_datetime(wide.index)
        wide = wide.sort_index()
        return wide

    async def correlations(
        self, user_id: int, start: date, end: date
    ) -> pd.DataFrame:
        df = await self.daily_summary(user_id, start, end)
        if df.empty or df.shape[1] < 2:
            return pd.DataFrame()
        return df.corr(numeric_only=True)
