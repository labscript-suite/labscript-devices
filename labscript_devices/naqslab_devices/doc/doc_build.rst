Building Documentation
======================

The API documentation for this library leverages the 
`Sphinx <http://www.sphinx-doc.org/en/master/index.html>`_ automatic python documenation generator.
The general structure is to use the :std:doc:`Sphinx-apidoc<sphinx:man/sphinx-apidoc>` infrastucture to read
source code docstrings to automatically build the function/class reference documentation for each device.
Hand-written ReStructedText files (`quick syntax guide <https://thomas-cokelaer.info/tutorials/sphinx/rest_syntax.html>`_) 
are then used to provide high-level documentation that imports
the auto-generated documentation. A makefile is provided to run the correct ``apidoc`` and
``sphinx-build`` commands.

Sphinx Environment
------------------

In order to build the documentation from scratch, a functioning ``labscript``
environment is needed with sphinx also installed. Because sphinx requires a large
amount of dependencies, it is recommended to copy your local ``labscript`` environment
then install and use sphinx from there.

Sphinx can be installed into the ``labscript`` environment by installing the packages:
``sphinx>=2.2`` and ``sphinx_rtd_theme``. This will allow building of the html documentation.

If you also wish to build the pdf documentation, you must also install ``perl``
and a latex environment (such as MikTeX for windows). The latex build is controlled
using the ``latexmk`` latex package and requires a great many other latex packages.
A partial list of required latex packages is: cmap, fncychap, tabulary, parskip, capt-of.

Sphinx Build
------------

The documentation build is automated through makefiles. All commands are run from
the :file:`doc` subfolder.

The automated documentation build is perfomed using

.. code-block:: bash
	
	make apidoc

The auto-generated files are placed in the :file:`_apidoc` subfolder of :file:`doc`
and are given the import name of the module with the file suffix ``.inc``.

The complete documentation is built using ``sphinx-build`` and currently supports
two targets: html and latexpdf. They are run using 

.. code-block:: bash
	
	make html
	#or
	make latexpdf

Adding Documentation
--------------------

The main documentation tree is found in :file:`index.rst`. New devices should be
added using :file:`devices.rst`. Each device should have it's own rst file that 
provides some high-level documentation and includes the auto-generated apidoc file.
All modules and submodules in the top-level directory of the library will have
documentation auto-generated using apidoc. It is up to the user to include those
files where appropriate in the documenation. The include statement is of the form:

.. code:: rst
	
	.. include:: _apidoc\naqslab_devices.NovaTechDDS.inc
