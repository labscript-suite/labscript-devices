# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------

project = 'naqslab_devices'
copyright = '2019, dihm'
author = 'dihm'

# The full version, including alpha/beta/rc tags
from naqslab_devices import __version__
# short version
version = __version__
# long version
release = version

# get version into rst files
#rst_epilog = '.. |version| replace:: %s' % version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
	'sphinx.ext.autodoc',
	'sphinx.ext.napoleon',
	'sphinx.ext.viewcode',
	'sphinx.ext.autosummary',
	'sphinx.ext.intersphinx',
	'sphinx.ext.coverage'
]

# disable viewcode from putting in source for imported libraries
viewcode_follow_imported_members = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The master toctree document.
master_doc = 'index'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# autosummary
#autosummary_generate = False

autoclass_content = "init" # options: "both", "class", "init"

autodoc_default_options = {
		"members":True,
		"undoc-members":True,
		"show-inheritance":True,
		"inherited-members":True,
		"member-order":'bysource', # 'alphabetical', 'groupwise', or 'bysource'
		#"private-members":True,
		#"special-members":True,
		#"imported-members":True,
		"exclude-members":''
}

needs_sphinx = '2.2'

add_module_names = True

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
#html_theme = 'alabaster'

import sphinx_rtd_theme

html_theme = "sphinx_rtd_theme"

html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
'papersize': 'a4paper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',

# Latex figure (float) alignment
'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
#latex_documents = [
#    (master_doc, 'naqslab_devices.tex', u'naqslab devices Documentation',
#     u'dihm', 'manual'),
#]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True

# -- Intersphinx Options --------------------------------------------------

# configure intersphinx to attempt auto-lookup of objects inventory.
# If it fails, use local cached copy.
intersphinx_mapping = {'pyvisa':('https://pyvisa.readthedocs.io/en/latest/',(None,'_inv/pyvisa-objects.inv')),
					   'sphinx':('http://www.sphinx-doc.org/en/master/',(None,'_inv/sphinx-objects.inv'))}
