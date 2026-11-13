// Shared schema constants and records (docs/SCHEMAS.md). Quantities: int64 units. Prices: int64 paise. Times: UTC epoch seconds.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>
namespace pe {
using i64 = std::int64_t;
struct EngineError : std::runtime_error { using std::runtime_error::runtime_error; };
struct EventValidationError : EngineError { using EngineError::EngineError; };
struct ModeContaminationError : EngineError { using EngineError::EngineError; };
struct InvariantViolation : EngineError { using EngineError::EngineError; };

constexpr i64 kIstOffsetS = 19800;
constexpr i64 kTickPaise = 5;
inline const char* kSchemaFill = "pe.fill.v1";
inline const std::vector<std::string> kModes = {"HISTORICAL_OBSERVED_REPLAY", "RESEARCH_POLICY_SIMULATION", "SYNTHETIC_TEST"};
inline const std::vector<std::string> kEventColumns = {"schema_version", "execution_mode", "fill_id", "source_row_id", "parent_order_id", "module_tag", "instrument_id", "timestamp_s", "side", "quantity",
                                                       "price_paise", "requested_quantity", "order_status", "is_duplicate_fill", "evidence_source"};
inline const std::vector<std::string> kInstrumentColumns = {"instrument_id", "underlying", "exchange_segment", "instrument_type", "option_type", "strike", "expiry", "lot_size", "tick_size_paise", "lot_size_source"};
inline const std::vector<std::string> kWarnCodes = {"DUPLICATE_FILL_IGNORED", "INPUT_NOT_TIME_ORDERED", "TIE_GROUP_MIXED_SIDE", "PARTIAL_FILL_ROWS", "UNFILLED_REMAINDER_ORDERS", "OVERFILLED_ORDERS",
                                                    "PARENT_SPANS_DATES", "EXPIRED_UNCLOSED_INSTRUMENTS", "MISSING_MARKS"};

struct Instrument { std::string id, underlying, segment, type, option_type; i64 strike = 0; std::string expiry; i64 lot_size = 0, tick_paise = 0; std::string lot_source; i64 expiry_day = 0; bool is_call = true; };
struct Fill {
  std::string fill_id; i64 source_row = 0; std::string parent_id, module_tag, instrument_id; i64 ts = 0; int side = 0; i64 qty = 0, price = 0, requested = 0; std::string status; bool duplicate = false; std::string mode, evidence; i64 line = 0;
};

// days since 1970-01-01 <-> civil date (same algorithm as python/pe/schema.py)
inline i64 days_from_civil(i64 y, i64 m, i64 d) {
  y -= m <= 2; const i64 era = (y >= 0 ? y : y - 399) / 400; const i64 yoe = y - era * 400; const i64 doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1; const i64 doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + doe - 719468;
}
inline void civil_from_days(i64 z, i64& y, i64& m, i64& d) {
  z += 719468; const i64 era = (z >= 0 ? z : z - 146096) / 146097; const i64 doe = z - era * 146097; const i64 yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; y = yoe + era * 400;
  const i64 doy = doe - (365 * yoe + yoe / 4 - yoe / 100); const i64 mp = (5 * doy + 2) / 153; d = doy - (153 * mp + 2) / 5 + 1; m = mp + (mp < 10 ? 3 : -9); y += (m <= 2);
}
inline std::string fmt6(double x) { char b[64]; std::snprintf(b, sizeof b, "%.6f", x); return b; }
inline i64 checked_mul(i64 a, i64 b) { i64 r; if (__builtin_mul_overflow(a, b, &r)) throw InvariantViolation("int64 overflow in P&L arithmetic"); return r; }
inline i64 checked_add(i64 a, i64 b) { i64 r; if (__builtin_add_overflow(a, b, &r)) throw InvariantViolation("int64 overflow in P&L arithmetic"); return r; }
inline i64 ist_day(i64 ts) { return (ts + kIstOffsetS) / 86400; }
inline std::string day_iso(i64 day) { i64 y, m, d; civil_from_days(day, y, m, d); char b[64]; std::snprintf(b, sizeof b, "%04lld-%02lld-%02lld", (long long)y, (long long)m, (long long)d); return b; }
inline i64 iso_day(const std::string& s) {
  if (s.size() != 10 || s[4] != '-' || s[7] != '-') throw EventValidationError("bad date " + s);
  return days_from_civil(std::stoll(s.substr(0, 4)), std::stoll(s.substr(5, 2)), std::stoll(s.substr(8, 2)));
}
}  // namespace pe
