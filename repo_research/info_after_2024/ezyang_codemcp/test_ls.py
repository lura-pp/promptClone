#!/usr/bin/env python3

"""Tests for the LS subtool."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class LSTest(MCPEndToEndTestCase):
    """Test the LS subtool."""

    async def test_ls(self):
        """Test the LS subtool."""
        # Create a test directory structure
        test_dir = os.path.join(self.temp_dir.name, "test_directory")
        os.makedirs(test_dir)

        with open(os.path.join(test_dir, "file1.txt"), "w") as f:
            f.write("Content of file 1")

        with open(os.path.join(test_dir, "file2.txt"), "w") as f:
            f.write("Content of file 2")

        # Create a subdirectory
        sub_dir = os.path.join(test_dir, "subdirectory")
        os.makedirs(sub_dir)

        with open(os.path.join(sub_dir, "subfile.txt"), "w") as f:
            f.write("Content of subfile")

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for LS test",
                    "subject_line": "test: initialize for LS test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the LS tool with chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {"subtool": "LS", "path": test_dir, "chat_id": chat_id},
            )

            # Verify the result includes all files and directories
            self.assertIn("file1.txt", result_text)
            self.assertIn("file2.txt", result_text)
            self.assertIn("subdirectory", result_text)


if __name__ == "__main__":
    unittest.main()
