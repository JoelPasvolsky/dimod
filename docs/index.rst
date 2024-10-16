..  -*- coding: utf-8 -*-

=====
dimod
=====

.. this file is used for testing docbuilds locally. For production
    documentation, update the sdk_index.rst file. 

.. include:: README.rst
  :start-after: index-start-marker1
  :end-before: index-end-marker1

(For explanations of the terminology, see the
:ref:`section_concepts_glossary` section.)

Example Usage
-------------

Find all solutions to a two-variable BQM using dimod's 
:class:`~dimod.reference.samplers.ExactSolver` reference
sampler, a brute-force solver useful for testing code on small problems.

.. include:: README.rst
  :start-after: index-start-marker2
  :end-before: index-end-marker2

Documentation
-------------

.. note:: For updates to production documentation, ensure that the sdk_index.rst 
    file is also updated.

.. sdk-start-marker

.. toctree::
  :maxdepth: 1

  reference/index
  release_notes

.. sdk-end-marker

.. toctree::
  :caption: Code
  :maxdepth: 1

  Source <https://github.com/dwavesystems/dimod>
  installation
  license

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
