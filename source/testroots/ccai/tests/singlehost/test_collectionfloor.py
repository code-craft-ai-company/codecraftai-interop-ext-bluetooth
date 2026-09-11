"""
    A floor on the number of tests the merge gate collects, so a discovery regression (a wrong
    ``--includes`` prefix, an import error in a test module) fails loudly instead of quietly running
    fewer tests.
"""

import ast
import os

from ccai.testbase.testcollector import TestCollector

# The include expression the merge gate passes (see .github/workflows/merge_gate.yml).  Include
# expressions are rooted at the parent of --root, so the leading segment is the root's directory name.
GATE_INCLUDE_EXPRESSION = "ccai.tests.singlehost"

# The prefix testbase uses to recognise test functions.
TEST_METHOD_PREFIX = "test"

# The number of tests this suite collected when the floor was set (test coverage roadmap, Phase 3a).
# Raise it when tests are added; never lower it without an explanation in the commit.
COLLECTED_TEST_FLOOR = 42


def find_test_root(start_file: str) -> str:
    """
        Walks up from a file inside the test tree to the directory holding ``__testroot__.py``,
        which is the directory the gate passes as ``--root``.

        :param start_file: The path of a module inside the test root.

        :returns: The absolute path of the test root directory.
        :raises: RuntimeError
    """
    current = os.path.dirname(os.path.abspath(start_file))
    while True:
        marker = os.path.join(current, "__testroot__.py")
        if os.path.exists(marker):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("No __testroot__.py found above {!r}".format(start_file))
        current = parent


def count_tests_with_collector(root: str, include_expression: str) -> int:
    """
        Counts tests exactly as the gate does: a :class:`TestCollector` over ``root`` fed the gate's
        include expression, with no excludes or metadata filters.

        :param root: The test root directory (the gate's ``--root``).
        :param include_expression: The gate's ``--includes`` value.

        :returns: The number of test references collected.
        :raises: AssertionError when the collector reports an import error, since that is exactly the
                 regression the floor exists to catch.
    """
    collector = TestCollector(root, excludes=[], metafilters=[])
    collector.collect_references(include_expression)

    import_errors = collector.import_errors
    if len(import_errors) > 0:
        err_msg_lines = ["The test collector reported import errors:"]
        for modname, ifile, errmsg in import_errors.values():
            err_msg_lines.append("    {} ({}): {}".format(modname, ifile, errmsg))
        err_msg = os.linesep.join(err_msg_lines)
        raise AssertionError(err_msg)

    collected = len(collector.references)
    return collected


def count_tests_by_ast(root: str, include_expression: str) -> int:
    """
        Fallback count that needs no imports: parses every ``test_*.py`` module under the directory
        the include expression names and counts its module-level ``test*`` functions.

        :param root: The test root directory.
        :param include_expression: The gate's include expression; segments after the first map to
                                   directories under ``root``.

        :returns: The number of module-level test functions found.
    """
    segments = include_expression.split(".")
    subtree = os.path.join(root, *segments[1:])

    counted = 0
    for dirpath, dirnames, filenames in os.walk(subtree):
        for filename in filenames:
            if not filename.startswith("test_") or not filename.endswith(".py"):
                continue
            module_path = os.path.join(dirpath, filename)
            with open(module_path, "r", encoding="utf-8") as module_file:
                tree = ast.parse(module_file.read(), filename=module_path)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith(TEST_METHOD_PREFIX):
                        counted += 1

    return counted


def test_gate_collects_at_least_the_floor() -> None:
    """
        The gate's collection (``--root`` of this test root, ``--includes`` of the gate's expression)
        yields at least ``COLLECTED_TEST_FLOOR`` tests.

        Mechanism: the count is produced by the same :class:`ccai.testbase.testcollector.TestCollector`
        the runner uses, over the same root and include expression, so it drops whenever discovery
        would drop -- a module that fails to import, a renamed directory, a prefix that no longer
        matches.  The AST-based count is computed alongside as an import-free cross-check; the two
        agree unless a module defines test functions the collector cannot see.
    """
    root = find_test_root(__file__)

    collected = count_tests_with_collector(root, GATE_INCLUDE_EXPRESSION)
    parsed = count_tests_by_ast(root, GATE_INCLUDE_EXPRESSION)

    if collected < COLLECTED_TEST_FLOOR:
        raise AssertionError("The gate collects {} tests under {!r}, below the floor of {}.".format(collected, GATE_INCLUDE_EXPRESSION, COLLECTED_TEST_FLOOR))

    if parsed != collected:
        raise AssertionError("The collector found {} tests but the source tree defines {}; a test module is not being discovered.".format(collected, parsed))

    return
