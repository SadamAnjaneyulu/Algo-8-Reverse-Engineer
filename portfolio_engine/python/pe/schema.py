"""Shared schema constants and records. See docs/SCHEMAS.md. Quantities are integer units, prices integer paise, times UTC epoch seconds."""
from dataclasses import dataclass

SCHEMA_FILL = 'pe.fill.v1'
MODES = ('HISTORICAL_OBSERVED_REPLAY', 'RESEARCH_POLICY_SIMULATION', 'SYNTHETIC_TEST')
METHODS = ('FIFO', 'LIFO', 'AVG')
TIE_ORDERS = ('src', 'sells_first', 'buys_first')
IST_OFFSET_S = 19800
TICK_PAISE = 5
EVENT_COLUMNS = ['schema_version', 'execution_mode', 'fill_id', 'source_row_id', 'parent_order_id', 'module_tag', 'instrument_id', 'timestamp_s', 'side', 'quantity', 'price_paise',
                 'requested_quantity', 'order_status', 'is_duplicate_fill', 'evidence_source']
INSTRUMENT_COLUMNS = ['instrument_id', 'underlying', 'exchange_segment', 'instrument_type', 'option_type', 'strike', 'expiry', 'lot_size', 'tick_size_paise', 'lot_size_source']
# fixed order of warning codes in every dump (both languages)
WARN_CODES = ['DUPLICATE_FILL_IGNORED', 'INPUT_NOT_TIME_ORDERED', 'TIE_GROUP_MIXED_SIDE', 'PARTIAL_FILL_ROWS', 'UNFILLED_REMAINDER_ORDERS', 'OVERFILLED_ORDERS', 'PARENT_SPANS_DATES',
              'EXPIRED_UNCLOSED_INSTRUMENTS', 'MISSING_MARKS']


class EngineError(Exception): pass
class EventValidationError(EngineError): pass
class ModeContaminationError(EngineError): pass
class InvariantViolation(EngineError): pass


@dataclass(frozen=True)
class Instrument:
    instrument_id: str; underlying: str; exchange_segment: str; instrument_type: str; option_type: str; strike: int; expiry: str; lot_size: int; tick_size_paise: int; lot_size_source: str


@dataclass(frozen=True)
class Fill:
    fill_id: str; source_row_id: int; parent_order_id: str; module_tag: str; instrument_id: str; timestamp_s: int; side: int; quantity: int; price_paise: int
    requested_quantity: int; order_status: str; is_duplicate_fill: bool; execution_mode: str; evidence_source: str; line: int = 0


def days_from_civil(y, m, d):
    """days since 1970-01-01 (proleptic Gregorian); identical algorithm in the C++ core"""
    y -= m <= 2; era = (y if y >= 0 else y - 399) // 400; yoe = y - era * 400; doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1; doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468; era = (z if z >= 0 else z - 146096) // 146097; doe = z - era * 146097; yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365; y = yoe + era * 400; doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153; d = doy - (153 * mp + 2) // 5 + 1; m = mp + (3 if mp < 10 else -9); return y + (m <= 2), m, d


def ist_day(ts): return (ts + IST_OFFSET_S) // 86400
def day_iso(day): y, m, d = civil_from_days(day); return f'{y:04d}-{m:02d}-{d:02d}'
def iso_day(s): y, m, d = (int(x) for x in s.split('-')); return days_from_civil(y, m, d)
