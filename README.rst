====================================================================
Automation Mojo Bluetooth Interop Extension (automojo-interop-ext-bluetooth)
====================================================================
This repository contains the Automation Mojo interop extension for Bluetooth. It
provides the project scaffolding and package layout used to implement Bluetooth
interop capabilities that integrate with the broader Automation Mojo ecosystem.

========
Overview
========
* Python package for Automation Mojo Bluetooth interoperability extensions.
* Source code lives under ``source/packages``.
* Tooling and conventions are documented in the ``userguide`` directory.

====================
Development Workflow
====================
1. Run the repository homing script to generate the local ``.env`` file::

       ./repository-setup/rehome-repository

2. Create the virtual environment for the repository::

       ./development/setup-environment

3. Install dependencies with Poetry::

       poetry install

=================
Code Organization
=================
* ``development`` - Environment setup scripts for developers.
* ``repository-setup`` - Repository homing and machine setup scripts.
* ``source/packages`` - Package source roots.
* ``userguide`` - Coding standards, naming conventions, and testing guidance.

==========
References
==========
- `User Guide <userguide/userguide.rst>`_
- `Coding Standards <userguide/10-00-coding-standards.rst>`_
- `Naming Conventions <userguide/10-02-naming-conventions.rst>`_
- `Testing Frameworks <userguide/10-04-testing-frameworks.rst>`_
