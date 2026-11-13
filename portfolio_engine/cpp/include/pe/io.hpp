// TSV readers with the same validation as python/pe/tsvio.py. Integers are parsed strictly (the whole field must be a base-10 integer).
#pragma once
#include <charconv>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include "pe/types.hpp"
namespace pe {
inline std::vector<std::string> split_tab(const std::string& s) { std::vector<std::string> o; std::size_t a = 0; for (;;) { auto b = s.find('\t', a); if (b == std::string::npos) { o.push_back(s.substr(a)); break; } o.push_back(s.substr(a, b - a)); a = b + 1; } return o; }
inline i64 to_int(const std::string& f, const std::string& what, const std::string& where) {
  i64 v = 0; const char* b = f.data(); const char* e = b + f.size(); auto r = std::from_chars(b, e, v);
  if (f.empty() || r.ec != std::errc() || r.ptr != e) throw EventValidationError(where + ": " + what + "=" + f + " is not an integer");
  return v;
}
template <class F> void for_rows(const std::string& path, const std::vector<std::string>& header, F&& fn) {
  std::ifstream in(path); if (!in) throw EventValidationError("cannot open " + path);
  std::string line; i64 n = 0; bool have_header = false;
  while (std::getline(in, line)) {
    ++n; if (line.empty() || line[0] == '#') continue; auto p = split_tab(line);
    if (!have_header) { if (p != header) throw EventValidationError(path + ": bad header"); have_header = true; continue; }
    if (p.size() != header.size()) throw EventValidationError(path + ":" + std::to_string(n) + ": wrong number of fields");
    fn(n, p);
  }
}
inline std::map<std::string, Instrument> read_instruments(const std::string& path) {
  std::map<std::string, Instrument> out;
  for_rows(path, kInstrumentColumns, [&](i64 n, const std::vector<std::string>& p) {
    const std::string w = path + ":" + std::to_string(n); Instrument i; i.id = p[0]; i.underlying = p[1]; i.segment = p[2]; i.type = p[3]; i.option_type = p[4]; i.strike = to_int(p[5], "strike", w); i.expiry = p[6];
    i.lot_size = to_int(p[7], "lot_size", w); i.tick_paise = to_int(p[8], "tick_size_paise", w); i.lot_source = p[9];
    if (i.option_type != "CE" && i.option_type != "PE") throw EventValidationError(w + ": invalid option_type " + i.option_type);
    i.is_call = i.option_type == "CE"; try { i.expiry_day = iso_day(i.expiry); } catch (const std::exception&) { throw EventValidationError(w + ": bad expiry " + i.expiry); }
    if (out.count(i.id)) throw EventValidationError(w + ": duplicate instrument " + i.id);
    out[i.id] = i;
  });
  return out;
}
inline std::vector<Fill> read_events(const std::string& path, const std::map<std::string, Instrument>& ins) {
  std::vector<Fill> fills; std::set<std::string> seen;
  for_rows(path, kEventColumns, [&](i64 n, const std::vector<std::string>& p) {
    const std::string w = path + ":" + std::to_string(n); Fill f; f.line = n;
    if (p[0] != kSchemaFill) throw EventValidationError(w + ": schema_version " + p[0]);
    bool okm = false;
    for (auto& m : kModes) okm = okm || (m == p[1]);
    if (!okm) throw EventValidationError(w + ": unknown execution_mode " + p[1]);
    f.mode = p[1]; f.fill_id = p[2]; f.source_row = to_int(p[3], "source_row_id", w); f.parent_id = p[4]; f.module_tag = p[5]; f.instrument_id = p[6]; f.ts = to_int(p[7], "timestamp_s", w);
    const i64 side = to_int(p[8], "side", w); f.qty = to_int(p[9], "quantity", w); f.price = to_int(p[10], "price_paise", w); f.requested = to_int(p[11], "requested_quantity", w); f.status = p[12];
    const i64 dup = to_int(p[13], "is_duplicate_fill", w); f.evidence = p[14];
    if (side != 1 && side != -1) throw EventValidationError(w + ": side must be +1 or -1");
    f.side = (int)side;
    if (f.qty <= 0) throw EventValidationError(w + ": quantity must be positive");
    if (f.price <= 0 || f.price % kTickPaise) throw EventValidationError(w + ": price_paise is not a positive multiple of the tick");
    if (f.ts <= 0) throw EventValidationError(w + ": bad timestamp");
    if (!ins.count(f.instrument_id)) throw EventValidationError(w + ": unknown instrument " + f.instrument_id);
    if (!seen.insert(f.fill_id).second) throw EventValidationError(w + ": duplicate fill_id " + f.fill_id + " (a fill is applied exactly once)");
    if (dup != 0 && dup != 1) throw EventValidationError(w + ": is_duplicate_fill must be 0/1");
    f.duplicate = dup == 1;
    if (f.status != "Filled" && f.status != "PartiallyFilled") throw EventValidationError(w + ": order_status " + f.status);
    fills.push_back(std::move(f));
  });
  return fills;
}
}  // namespace pe
