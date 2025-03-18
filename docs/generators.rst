.. _dimod_generators:

===================================
Generators and Application Modeling
===================================

.. currentmodule:: dimod.generators

.. automodule:: dimod.generators

Benchmarking
============

.. autosummary::
   :toctree: generated/

   anti_crossing_clique
   anti_crossing_loops
   chimera_anticluster
   doped
   frustrated_loop
   random_2in4sat
   random_nae3sat

Constraints
===========

.. autosummary::
   :toctree: generated/

   and_gate
   binary_encoding
   combinations
   fulladder_gate
   halfadder_gate
   multiplication_circuit
   or_gate
   xor_gate

Optimization
============

.. autosummary::
   :toctree: generated/

   bin_packing
   coordinated_multipoint
   independent_set
   knapsack
   maximum_independent_set
   maximum_weight_independent_set
   mimo
   multi_knapsack
   quadratic_assignment
   quadratic_knapsack
   quadratic_multi_knapsack
   random_bin_packing
   random_knapsack
   random_multi_knapsack

Random
======

.. autosummary::
   :toctree: generated/

   doped
   gnm_random_bqm
   gnp_random_bqm
   randint
   random_2in4sat
   random_bin_packing
   random_knapsack
   random_multi_knapsack
   random_nae3sat
   ran_r
   uniform

.. _generators_symbolic_math:

Single-Variable Models
======================

Generators for single-variable models used in
:ref:`symbolic math <concept_symbolic_math>`.

.. currentmodule:: dimod

.. autosummary::
   :toctree: generated/

   ~binary.Binary
   ~binary.Binaries
   ~binary.BinaryArray
   ~quadratic.Integer
   ~quadratic.Integers
   ~quadratic.IntegerArray
   ~binary.Spin
   ~binary.Spins
   ~binary.SpinArray
