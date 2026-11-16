// Adds a new plugin to the C++ simulation WITHOUT touching any framework header.
// Build and run from 02_Portfolio_Construction_Prototype (see 04_Documentation/02_How_To_Run_and_Inspect.docx):
//   g++ -std=c++17 -I cpp/include -I ../01_Historical_Position_Reconstruction/cpp/include examples/add_a_plugin.cpp -o /tmp/add_a_plugin && /tmp/add_a_plugin
#include <fstream>
#include <iostream>
#include <sstream>
#include "pc/engine.hpp"

struct FlattenLeg : pc::Plugin {              // cuts the whole long put wing once the configured time is reached
  std::string name() const override { return "flatten_leg"; }
  std::string version() const override { return "1.0.0"; }
  std::vector<std::pair<std::string, pc::Spec>> spec() const override { return {{"at_ts", pc::ispec(0, true, 0, true, 100000000000LL)}}; }
  void evaluate(const pc::EvalContext& ctx, pc::PluginResult& r) const override {      // ctx holds only data with timestamp <= ctx.ts
    for (auto& b : ctx.baskets)
      for (auto& l : b.legs)
        if (l.leg_id == "WPE" && l.current > 0 && ctx.ts >= geti("at_ts")) {
          r.actions.push_back({name() + "|" + std::to_string(ctx.ts) + "|" + b.basket_id, name(), version(), "CUT", "", b.basket_id, l.leg_id, l.current, "", ctx.ts, ctx.ts, "FLATTEN"});
          r.status = "OK";
        }
  }
};

int main() {
  std::ifstream in("scenarios/s05_reentry_success.scn"); std::stringstream ss; ss << in.rdbuf(); std::string text = ss.str();
  long long first_tick = 0; { std::istringstream is(text); std::string line; while (std::getline(is, line)) if (line.rfind("TICK\t", 0) == 0) { first_tick = std::stoll(line.substr(5)); break; } }
  text += "PLUGIN\tflatten_leg\t1.0.0\t1\nCONFIG\tflatten_leg\tat_ts\t" + std::to_string(first_tick + 600) + "\n";
  pc::Catalog catalog; catalog["flatten_leg"] = [] { return std::make_shared<FlattenLeg>(); };      // register the new plugin by name
  pc::Simulation sim(pc::Scenario::parse(text), catalog); auto files = sim.files();
  std::istringstream actions(files["actions.tsv"]); std::string row;
  while (std::getline(actions, row)) { if (row.empty() || row[0] == '#') continue; std::vector<std::string> f = pc::split(row, '\t'); if (f[3] == "flatten_leg") std::cout << "t+" << std::stoll(f[1]) - first_tick << "s  flatten_leg proposed " << f[5] << " " << f[7] << ":" << f[8] << " qty " << f[9] << " -> " << f[12] << "\n"; }
  return 0;
}
