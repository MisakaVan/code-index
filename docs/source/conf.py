# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath("../../"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "code-index"
copyright = "2025, MisakaVan"
author = "MisakaVan"
release = "0.1.0"
version = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",  # generate documentation from docstrings
    "sphinx.ext.napoleon",  # support for Google and NumPy style docstrings
    "sphinx.ext.viewcode",  # add links to the source code
    "sphinx.ext.todo",  # support for todo directives
    "sphinx.ext.coverage",  # check documentation coverage
    "sphinx.ext.githubpages",  # generate .nojekyll file for GitHub Pages
    "sphinx.ext.intersphinx",  # link to other projects' documentation
    "sphinx.ext.autosummary",  # generate autodoc summaries
]

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__init__",
}

# Autosummary settings
autosummary_generate = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "tree_sitter": ("https://tree-sitter.github.io/py-tree-sitter/", None),
}

templates_path = ["_templates"]
exclude_patterns = []

# The master toctree document
master_doc = "index"

# Source file suffixes
source_suffix = ".rst"


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    # 仓库相关设置
    "repository_url": "https://github.com/MisakaVan/code_index",  # GitHub 仓库链接
    "repository_branch": "main",  # 默认分支名
    "use_repository_button": True,  # 显示 GitHub 按钮
    "use_edit_page_button": True,  # 显示编辑页面按钮
    "use_source_button": True,  # 显示查看源代码按钮
    "use_issues_button": True,  # 显示问题报告按钮
    "use_download_button": True,  # 显示下载按钮
    # 导航和布局设置
    "show_navbar_depth": 2,  # 导航栏显示的层级深度
    "show_toc_level": 1,  # 目录显示的层级深度 (限制为1层，避免方法级别显示)
    "collapse_navigation": False,  # 是否折叠导航菜单
    "navigation_with_keys": True,  # 允许键盘导航
    "show_prev_next": True,  # 显示上一页/下一页按钮
    # 搜索设置
    "use_sidenotes": True,  # 启用侧边注释
    "announcement": "",  # 页面顶部公告（可选）
    # 页面布局设置
    "home_page_in_toc": True,  # 在目录中包含首页
    "use_fullscreen_button": True,  # 显示全屏按钮
    # 外观设置
    "logo": {
        # "image_light": "_static/logo-light.png",  # 浅色主题 logo
        # "image_dark": "_static/logo-dark.png",   # 深色主题 logo
        # "text": "Code Index",  # 文字 logo
    },
    # 页脚设置
    "extra_footer": "",  # 额外的页脚内容
    # 高级设置
    "path_to_docs": "docs",  # 文档相对于仓库根目录的路径
    "launch_buttons": {
        # "binderhub_url": "",  # Binder 启动按钮
        # "jupyterhub_url": "",  # JupyterHub 启动按钮
        # "colab_url": "",  # Google Colab 启动按钮
    },
}

html_title = f"{project} {version} documentation"
html_short_title = project

# Add any paths that contain custom static files (such as style sheets)
html_static_path = ["_static"]

# If true, links to the reST sources are added to the pages
html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer
html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer
html_show_copyright = True
