# Plain make alternative to CMake:  make && make test
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wno-misleading-indentation -ffp-contract=off -Iinclude
SRC = src/d1_engine.cpp src/d0_engine.cpp src/backtest.cpp
all: build/algo8_backtest build/dump_cycle build/test_util
build/algo8_backtest: $(SRC) src/main_backtest.cpp include/algo8/*.hpp
	@mkdir -p build && $(CXX) $(CXXFLAGS) $(SRC) src/main_backtest.cpp -o $@ -lpthread
build/dump_cycle: $(SRC) tools/dump_cycle.cpp include/algo8/*.hpp
	@mkdir -p build && $(CXX) $(CXXFLAGS) $(SRC) tools/dump_cycle.cpp -o $@ -lpthread
build/test_util: tests/test_util.cpp include/algo8/util.hpp
	@mkdir -p build && $(CXX) $(CXXFLAGS) tests/test_util.cpp -o $@
test: all
	build/test_util && bash tests/run_parity.sh build
clean:
	rm -rf build
