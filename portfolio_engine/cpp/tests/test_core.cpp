// Core accounting tests (no framework dependency). Hand-computed expectations; the same scenarios exist in python/tests.
#include <iostream>
#include "pe/io.hpp"
#include "pe/replay.hpp"
using namespace pe;
static int failures = 0, checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
static std::map<std::string, Instrument> ins1(const std::string& id = "NIFTY|2026-01-08|CE|24000") { Instrument i; i.id = id; i.underlying = "NIFTY"; i.option_type = "CE"; i.is_call = true; i.expiry = "2026-01-08"; i.expiry_day = iso_day(i.expiry); i.lot_size = 65; i.tick_paise = 5; return {{id, i}}; }
static Fill F(const std::string& id, i64 row, i64 ts, int side, i64 q, i64 px, bool dup = false, const std::string& mode = "SYNTHETIC_TEST") {
  Fill f; f.fill_id = id; f.source_row = row; f.parent_id = "p" + id; f.instrument_id = "NIFTY|2026-01-08|CE|24000"; f.ts = 1767587000 + ts; f.side = side; f.qty = q; f.price = px; f.requested = q; f.status = "Filled"; f.duplicate = dup; f.mode = mode; return f; }
static i64 total_i(const std::string& dump, const std::string& name) { auto p = dump.find("TOTAL\t" + name + "\t"); auto a = p + 7 + name.size(); return std::stoll(dump.substr(a, dump.find('\n', a) - a)); }
static std::vector<Fill> lots_scenario() { return {F("a", 1, 0, -1, 65, 10000), F("b", 2, 60, -1, 65, 12000), F("c", 3, 120, -1, 65, 14000), F("d", 4, 300, 1, 130, 9000)}; }
int main() {
  auto ins = ins1();
  { auto r = replay(lots_scenario(), ins, "SYNTHETIC_TEST", "FIFO", "src", 0, true); CHECK(total_i(r.dump, "realized_pnl_paise") == 260000); CHECK(total_i(r.dump, "remaining_units") == 65); }
  { auto r = replay(lots_scenario(), ins, "SYNTHETIC_TEST", "LIFO", "src", 0, true); CHECK(total_i(r.dump, "realized_pnl_paise") == 520000); }
  { auto r = replay(lots_scenario(), ins, "SYNTHETIC_TEST", "AVG", "src", 0, true); CHECK(r.dump.find("TOTAL\trealized_pnl_paise\t390000.000000") != std::string::npos); }
  { std::vector<Fill> f = {F("a", 1, 0, 1, 65, 5000), F("b", 2, 30, -1, 130, 6000), F("c", 3, 90, 1, 65, 5500)}; auto r = replay(f, ins, "SYNTHETIC_TEST", "FIFO", "src", 0, true);
    CHECK(total_i(r.dump, "reversal_fills") == 1); CHECK(total_i(r.dump, "reversal_units_reopened") == 65); CHECK(total_i(r.dump, "remaining_units") == 0); CHECK(total_i(r.dump, "realized_pnl_paise") == 65 * 1000 + 65 * 500); }
  { std::vector<Fill> f = {F("a", 1, 0, -1, 65, 10000), F("a2", 2, 0, -1, 65, 10000, true), F("b", 3, 60, 1, 65, 9000)}; auto r = replay(f, ins, "SYNTHETIC_TEST", "FIFO", "src", 0, true); CHECK(r.warnings["DUPLICATE_FILL_IGNORED"] == 1); CHECK(total_i(r.dump, "opened_units") == 65); }
  { std::vector<Fill> f = {F("a", 1, 0, -1, 65, 10000), F("b", 2, 60, 1, 65, 9000), F("c", 3, 60, -1, 65, 9500)};
    auto r1 = replay(f, ins, "SYNTHETIC_TEST", "FIFO", "sells_first", 0, true); auto r2 = replay(f, ins, "SYNTHETIC_TEST", "FIFO", "buys_first", 0, true); CHECK(r1.warnings["TIE_GROUP_MIXED_SIDE"] == 1); CHECK(r1.roles != r2.roles); }       // role depends on the tie order: documented, never resolved
  { bool thrown = false; try { replay({F("a", 1, 0, -1, 65, 10000, false, "HISTORICAL_OBSERVED_REPLAY")}, ins, "SYNTHETIC_TEST", "FIFO", "src", 0, false); } catch (const ModeContaminationError&) { thrown = true; } CHECK(thrown); }
  { PortfolioState st(Method::FIFO, ins); st.apply_fill(F("a", 1, 0, -1, 65, 10000)); bool thrown = false; try { st.apply_fill(F("a", 1, 0, -1, 65, 10000)); } catch (const InvariantViolation&) { thrown = true; } CHECK(thrown); }     // a fill is applied exactly once
  { PortfolioState st(Method::FIFO, ins); st.apply_fill(F("a", 1, 0, -1, 65, 10000)); st.apply_fill(F("b", 2, 10, 1, 65, 9000)); CHECK(st.signed_inventory("NIFTY|2026-01-08|CE|24000") == 0); }
  std::cout << (checks - failures) << "/" << checks << " core checks passed\n"; return failures ? 1 : 0;
}
