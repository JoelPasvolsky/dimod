ROOT := ../
SRC := $(ROOT)/dimod/include/

all: catch2 test_main test_main_parallel tests tests_parallel

tests: test_main.out
	./test_main 

tests_parallel: test_main_parallel.out
	./test_main_parallel

test_main: test_main.cpp
	g++ -std=c++11 -Wall -c test_main.cpp
	g++ -std=c++11 -Wall test_main.o tests/*.cpp $(ROOT)/dimod/roof_duality/src/fix_variables.cpp -o test_main -I $(SRC)

test_main_parallel: test_main.cpp
	g++ -std=c++11 -fopenmp -Wall -c test_main.cpp -o test_main_parallel.o
	g++ -std=c++11 -fopenmp -Wall test_main_parallel.o tests/*.cpp $(ROOT)/dimod/roof_duality/src/fix_variables.cpp -o test_main_parallel -I $(SRC)

catch2:
	git submodule init
	git submodule update
