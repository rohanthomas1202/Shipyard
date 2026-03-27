# Deferred Items - Phase 04

## Pre-existing Test Failures (Out of Scope)

1. **test_ast_ops.py::TestExecutorInvalidation::test_executor_sets_invalidated_files** - executor_node became async but test doesn't await the coroutine
2. **test_editor_node.py::test_editor_node_successful_edit** - TypeError, likely related to async migration of editor_node
