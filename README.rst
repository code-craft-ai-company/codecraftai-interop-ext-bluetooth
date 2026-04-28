==============================================
Automation Mojo Interop Extension: Bluetooth
==============================================

The ``automojo-interop-ext-bluetooth`` package provides Bluetooth protocol interop extensions and landscape extensions that allow for interoperability with Bluetooth devices during automation runs. It plugs into the ``automojo-interop`` and ``automojo-landscaping`` frameworks through the extension mechanism in ``automojo-extension``.

Highlights
==========

- Bluetooth protocol handlers under ``interop/bluetooth/``.
- Landscape extension hooks so Bluetooth devices surface as first-class landscape resources.
- Composable with other ``automojo-interop-ext-*`` packages through the shared extension mechanism.

Repository Structure
====================

- ``development/`` - Runtime environment scripts.
- ``repository-setup/`` - Repository homing and setup scripts.
- ``source/packages/`` - Package source code.
- ``source/testroots/automojo/`` - TestBase test roots.
- ``userguide/`` - Standards, conventions, and documentation.

Environment Setup
=================

When working in a Codex container:

.. code-block:: bash

   ./development/setup-agent-container

For local development:

.. code-block:: bash

   ./repository-setup/rehome-repository
   ./development/setup-envrionment

Running Tests
=============

Activate the virtual environment:

.. code-block:: bash

   source .venv/bin/activate

Run the single-host test suite:

.. code-block:: bash

   testbase testing run --root source/testroots/automojo --includes=automojo.tests.singlehost.interop --output=./.output

Standards and Conventions
=========================

- Naming conventions: ``userguide/10-02-naming-conventions.rst``
- Code organization: ``userguide/10-01-code-organization.rst``
- Coding standards: ``userguide/10-00-coding-standards.rst``

Additional Resources
====================

- User guide entry point: ``userguide/userguide.rst``
