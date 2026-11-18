// pc_run <scenario.scn> <out_dir> : run one synthetic scenario and write the seven output files (same files as python -m pc.cli run).
#include <fstream>
#include <iostream>
#include <sstream>
#include "pc/engine.hpp"
int main(int argc, char** argv) {
  if (argc != 3) { std::cerr << "usage: pc_run <scenario.scn> <out_dir>\n"; return 2; }
  try {
    std::ifstream in(argv[1], std::ios::binary); if (!in) { std::cerr << "ERROR: cannot read " << argv[1] << "\n"; return 2; }
    std::stringstream ss; ss << in.rdbuf(); pc::Simulation sim(pc::Scenario::parse(ss.str())); sim.write(argv[2]); std::cout << "wrote " << argv[2] << "\n";
  } catch (const std::exception& e) { std::cerr << "ERROR: " << e.what() << "\n"; return 2; }
  return 0;
}
