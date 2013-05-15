from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(
	name='ckanext-edawax_theme',
	version=version,
	description="edawax specific layout",
	long_description="""\
	""",
	classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
	keywords='',
	author='Hendrik Bunke',
	author_email='h.bunke@zbw.eu',
	url='',
	license='',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	namespace_packages=['ckanext', 'ckanext.edawax_theme'],
	include_package_data=True,
	zip_safe=False,
	install_requires=[
		# -*- Extra requirements: -*-
	],
	entry_points=\
	"""
        [ckan.plugins]
	# Add plugins here, eg
	# myplugin=ckanext.edawax_theme:PluginClass
    edawax_theme=ckanext.edawax_theme.plugin:EdawaxThemePlugin
	""",
)
