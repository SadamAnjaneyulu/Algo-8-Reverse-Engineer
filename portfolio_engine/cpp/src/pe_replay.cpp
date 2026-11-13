// pe_replay --events E --instruments I --mode MODE [--method FIFO] [--tie src] [--snapshot-interval N] [--strict] [--dump F] [--roles F]
// Exit codes: 0 ok, 2 validation / mode / invariant error (message on stderr).
#include <cstring>
#include <fstream>
#include <iostream>
#include "pe/io.hpp"
#include "pe/replay.hpp"
int main(int argc, char** argv) {
  std::string events, instruments, mode, method = "FIFO", tie = "src", dump, roles; pe::i64 interval = 0; bool strict = false;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i]; auto next = [&]() -> std::string { if (i + 1 >= argc) { std::cerr << "ERROR: missing value for " << a << "\n"; std::exit(2); } return argv[++i]; };
    if (a == "--events") events = next(); else if (a == "--instruments") instruments = next(); else if (a == "--mode") mode = next(); else if (a == "--method") method = next(); else if (a == "--tie") tie = next();
    else if (a == "--snapshot-interval") interval = std::stoll(next()); else if (a == "--strict") strict = true; else if (a == "--dump") dump = next(); else if (a == "--roles") roles = next(); else { std::cerr << "ERROR: unknown argument " << a << "\n"; return 2; }
  }
  try {
    auto ins = pe::read_instruments(instruments); auto fills = pe::read_events(events, ins); auto res = pe::replay(fills, ins, mode, method, tie, interval, strict);
    if (!dump.empty()) { std::ofstream o(dump, std::ios::binary); o << res.dump; } if (!roles.empty()) { std::ofstream o(roles, std::ios::binary); o << res.roles; }
    std::cout << "OK events_applied=" << fills.size() << " checks=" << res.checks.size() << "\n"; return 0;
  } catch (const std::exception& e) { std::cerr << "ERROR: " << e.what() << "\n"; return 2; }
}
