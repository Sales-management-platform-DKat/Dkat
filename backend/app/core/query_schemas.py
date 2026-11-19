from datetime import date, datetime, time, timedelta, timezone

from pydantic import BaseModel, Field, field_validator, model_validator


class DatePageFilters(BaseModel):
    from_date: date | datetime | None = Field(default=None, alias="from")
    to_date: date | datetime | None = Field(default=None, alias="to")
    page: int = Field(default=1, ge=1, le=21474836)
    size: int = Field(default=50, ge=1, le=100)

    @field_validator("from_date", "to_date", mode="before")
    @classmethod
    def parse_date(cls, value):
        if not isinstance(value, str):
            return value
        try:
            if len(value) == 10:
                day = date.fromisoformat(value)
                if day.isoformat() == value:
                    return day
                raise ValueError
            if "T" not in value:
                raise ValueError
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Use YYYY-MM-DD or an ISO 8601 timestamp") from None

    @staticmethod
    def utc_bound(value: date | datetime | None, *, end: bool = False) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc)
            return value.replace(tzinfo=None)
        # A calendar date is interpreted in Vietnam. The end covers the full day.
        day_start = datetime.combine(value, time.min)
        return day_start - timedelta(hours=7) + (timedelta(days=1) if end else timedelta())

    @property
    def end_exclusive(self) -> bool:
        return self.to_date is not None and not isinstance(self.to_date, datetime)

    @model_validator(mode="after")
    def validate_period(self):
        try:
            start = self.utc_bound(self.from_date)
            end = self.utc_bound(self.to_date, end=True)
        except (ValueError, OverflowError):
            raise ValueError("Date is outside the permitted range") from None
        if start is not None and end is not None and (start > end or (start == end and self.end_exclusive)):
            raise ValueError("from must be at or before to")
        if any(bound is not None and bound.year < 1000 for bound in (start, end)):
            raise ValueError("Date is outside the permitted range")
        return self
