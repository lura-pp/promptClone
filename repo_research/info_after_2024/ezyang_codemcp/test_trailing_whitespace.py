#!/usr/bin/env python3

"""Tests for trailing whitespace stripping in the WriteFile and EditFile subtools."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class TrailingWhitespaceTest(MCPEndToEndTestCase):
    """Test that trailing whitespace is properly stripped when using WriteFile and EditFile."""

    async def test_write_file_strips_trailing_whitespace(self):
        """Test that the WriteFile subtool strips trailing whitespace from each line."""
        test_file_path = os.path.join(self.temp_dir.name, "write_whitespace.txt")

        # Content with trailing whitespace
        content_with_whitespace = "Line 1  \nLine 2 \t \nLine 3\n  Line 4  \n"

        # Expected content after whitespace stripping
        # The trailing newline is preserved
        expected_content = "Line 1\nLine 2\nLine 3\n  Line 4\n"

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for trailing whitespace test",
                    "subject_line": "test: initialize for trailing whitespace test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with content containing trailing whitespace
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content_with_whitespace,
                    "description": "Create file with trailing whitespace",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with trailing whitespace removed
            with open(test_file_path) as f:
                file_content = f.read()

            self.assertEqual(file_content, expected_content)

    async def test_edit_file_strips_trailing_whitespace(self):
        """Test that the EditFile subtool strips trailing whitespace from each line."""
        # Create a test file with multiple lines
        test_file_path = os.path.join(self.temp_dir.name, "edit_whitespace.txt")
        original_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        with open(test_file_path, "w") as f:
            f.write(original_content)

        # Add the file to git and commit it
        await self.git_run(["add", "edit_whitespace.txt"], check=False)
        await self.git_run(
            ["commit", "-m", "Add file for editing with whitespace"], check=False
        )

        # Edit the file with content containing trailing whitespace
        old_string = "Line 2\nLine 3\n"
        new_string_with_whitespace = "Line 2  \nModified Line 3 \t \n"

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for edit file whitespace test",
                    "subject_line": "test: initialize for edit file whitespace test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the EditFile tool with content containing trailing whitespace
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": old_string,
                    "new_string": new_string_with_whitespace,
                    "description": "Modify content with trailing whitespace",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully edited", result_text)

            # Verify the file was edited with trailing whitespace removed
            with open(test_file_path) as f:
                file_content = f.read()

            expected_content = "Line 1\nLine 2\nModified Line 3\nLine 4\nLine 5\n"
            self.assertEqual(file_content, expected_content)

    async def test_empty_lines_preserved(self):
        """Test that empty lines are preserved when stripping trailing whitespace."""
        test_file_path = os.path.join(self.temp_dir.name, "empty_lines.txt")

        # Content with empty lines and whitespace-only lines
        content_with_empty_lines = "Line 1\n\n \t \nLine 2\n"

        # Expected content after whitespace stripping
        # The whitespace-only line should become an empty line
        expected_content = "Line 1\n\n\nLine 2\n"

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for empty lines test",
                    "subject_line": "test: initialize for empty lines test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with content containing empty lines
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content_with_empty_lines,
                    "description": "Create file with empty lines",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with empty lines preserved
            with open(test_file_path) as f:
                file_content = f.read()

            self.assertEqual(file_content, expected_content)


class OutOfProcessTrailingWhitespaceTest(TrailingWhitespaceTest):
    in_process = False


if __name__ == "__main__":
    unittest.main()
