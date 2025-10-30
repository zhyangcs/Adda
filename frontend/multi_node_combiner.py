"""
Multi-Node Feature Combiner for In-Database ML
Combines feature transformations from multiple DAG nodes into unified SQL pipelines
"""

import pandas as pd
import networkx as nx
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class MultiNodeFeatureCombiner:
    """
    Combines feature transformations from multiple selected nodes in a DAG
    to create unified SQL pipelines for in-database ML training and testing.
    """

    def __init__(self, llm_dag_constructor, db_table_name: str, target_col: str):
        """
        Initialize the multi-node feature combiner.

        Args:
            llm_dag_constructor: The LLMDagConstructor instance containing the DAG
            db_table_name: Name of the database table
            target_col: Name of the target column
        """
        self.llm_dag_constructor = llm_dag_constructor
        self.db_table_name = db_table_name
        self.target_col = target_col
        self.dag = llm_dag_constructor.dag if llm_dag_constructor else None

    def validate_nodes(self, selected_node_ids: List[str]) -> Tuple[bool, str]:
        """
        Validate that all selected node IDs exist in the DAG.

        Args:
            selected_node_ids: List of selected node IDs

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.dag:
            return False, "DAG is not initialized"

        if not selected_node_ids:
            return False, "No nodes selected"

        # Check if DAG has any nodes
        dag_nodes = list(self.dag.nodes())
        if not dag_nodes:
            return False, "DAG contains no nodes. Please ensure the task is properly initialized."

        existing_node_ids = [str(n.node_id) for n in dag_nodes]
        invalid_nodes = [nid for nid in selected_node_ids if str(nid) not in existing_node_ids]

        if invalid_nodes:
            return False, f"Invalid node IDs: {invalid_nodes}"

        return True, ""

    def extract_feature_code_from_node(self, node_id: str) -> Optional[str]:
        """
        Extract the feature transformation code from a specific node.

        Args:
            node_id: ID of the node to extract code from

        Returns:
            Python code string for the feature transformation
        """
        if not self.dag:
            return None

        # Find the node in the DAG
        node = None
        for n in self.dag.nodes():
            if str(n.node_id) == str(node_id):  # 确保字符串比较
                node = n
                break

        if not node:
            logger.warning(f"Node {node_id} not found in DAG")
            return None

        # Get the feature code from the node based on LLMDAGNODE structure
        # 优先使用 whole_code，如果不存在则使用 task_code
        if hasattr(node, 'whole_code') and node.whole_code and node.whole_code.strip():
            return node.whole_code
        elif hasattr(node, 'task_code') and node.task_code and node.task_code.strip():
            return node.task_code
        else:
            logger.warning(f"No valid code found in node {node_id}")
            return None

    def sort_nodes_by_dependency(self, selected_node_ids: List[str]) -> List[str]:
        """
        Sort nodes based on their dependencies to ensure proper execution order.

        Args:
            selected_node_ids: List of selected node IDs

        Returns:
            Sorted list of node IDs in dependency order
        """
        if not self.dag:
            return selected_node_ids

        # Create a list of selected nodes
        selected_nodes = []
        dag_nodes = list(self.dag.nodes())
        if not dag_nodes:
            logger.warning("DAG has no nodes for dependency sorting")
            return selected_node_ids

        for n in dag_nodes:
            if str(n.node_id) in [str(nid) for nid in selected_node_ids]:
                selected_nodes.append(n)

        # Sort by distance from root (topological order)
        try:
            # Find root node (typically node_id = 1)
            root_node = None
            for n in self.dag.nodes():
                if hasattr(n, 'node_id') and str(n.node_id) == "1":
                    root_node = n
                    break

            if root_node:
                # Sort by shortest path distance from root
                sorted_nodes = sorted(selected_nodes,
                                    key=lambda n: len(nx.shortest_path(self.dag, root_node, n)))
                return [str(n.node_id) for n in sorted_nodes]
            else:
                # Fallback to original order if no root found
                return selected_node_ids
        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            # If dependency resolution fails, return original order
            logger.warning(f"Dependency resolution failed: {e}, returning original order")
            return selected_node_ids

    def combine_feature_codes(self, selected_node_ids: List[str]) -> Tuple[bool, str, Optional[str]]:
        """
        Combine feature transformation codes from multiple nodes into a unified pipeline.

        Args:
            selected_node_ids: List of selected node IDs

        Returns:
            Tuple of (success, error_message, combined_code)
        """
        # Validate nodes
        is_valid, error_msg = self.validate_nodes(selected_node_ids)
        if not is_valid:
            return False, error_msg, None

        # Sort nodes by dependency
        sorted_node_ids = self.sort_nodes_by_dependency(selected_node_ids)

        # Extract code from each node
        node_codes = []
        feature_columns = []

        for node_id in sorted_node_ids:
            code = self.extract_feature_code_from_node(node_id)
            if code is None:
                return False, f"Failed to extract code from node {node_id}", None

            node_codes.append(f"# Features from node {node_id}")
            node_codes.append(code)
            node_codes.append("")  # Add blank line between nodes

            # Extract feature column names from the node if possible
            node = None
            for n in self.dag.nodes():
                if n.node_id == node_id:
                    node = n
                    break

            if node and hasattr(node, 'out_cur_df') and node.out_cur_df is not None:
                if isinstance(node.out_cur_df, pd.DataFrame):
                    feature_columns.extend(list(node.out_cur_df.columns))

        # Create combined code
        combined_code_lines = [
            "# Combined feature pipeline from multiple nodes",
            f"# Selected nodes: {', '.join(sorted_node_ids)}",
            "",
            "import pandas as pd",
            "import numpy as np",
            "",
            f"def combined_feature_transform(df):",
            "    # Input: original dataframe",
            "    # Output: dataframe with all combined features",
            "    ",
            "    result_df = df.copy()",
            "    ",
        ]

        # Add each node's transformation
        for i, code in enumerate(node_codes):
            if code.startswith("#") or not code.strip():
                combined_code_lines.append(f"    {code}")
            else:
                # Smart indentation: preserve relative indentation
                lines = code.split('\n')
                # Calculate minimum indentation of the code block
                non_empty_lines = [line for line in lines if line.strip()]
                if non_empty_lines:
                    min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)

                    for line in lines:
                        if line.strip():  # Non-empty line
                            # Remove existing min indentation and add function indentation
                            adjusted_line = line[min_indent:]
                            combined_code_lines.append(f"    {adjusted_line}")
                        elif line == "":  # Empty line
                            combined_code_lines.append("    ")
                        else:  # Line with only whitespace
                            combined_code_lines.append("    ")
                else:
                    # If no non-empty lines, just indent each line
                    for line in lines:
                        combined_code_lines.append(f"    {line}")

        # Add final combination logic
        combined_code_lines.extend([
            "",
            "    return result_df",
            "",
            "# Execute the transformation",
            "df = combined_feature_transform(df)",
        ])

        combined_code = '\n'.join(combined_code_lines)

        return True, "", combined_code

    def get_combined_feature_info(self, selected_node_ids: List[str]) -> Dict:
        """
        Get information about the combined features from selected nodes.

        Args:
            selected_node_ids: List of selected node IDs

        Returns:
            Dictionary containing feature combination information
        """
        if not self.dag:
            return {"error": "DAG is not initialized"}

        # Validate nodes
        is_valid, error_msg = self.validate_nodes(selected_node_ids)
        if not is_valid:
            return {"error": error_msg}

        # Collect information from each node
        node_info = []
        total_features = 0

        for node_id in selected_node_ids:
            node = None
            for n in self.dag.nodes():
                if str(n.node_id) == str(node_id):
                    node = n
                    break

            if node:
                info = {
                    "node_id": node_id,
                    "operation_desc": getattr(node, 'operation_desc', 'Unknown operation'),
                    "final_score": getattr(node, 'final_score', 0.0),
                    "exec_time": getattr(node, 'exec_time', 0.0),
                    "feature_count": 0,
                    "op_type": str(getattr(node, 'op_type', 'Unknown'))
                }

                # Count features if available
                if hasattr(node, 'out_cur_df') and node.out_cur_df is not None:
                    if isinstance(node.out_cur_df, pd.DataFrame):
                        info["feature_count"] = len(node.out_cur_df.columns)
                        total_features += len(node.out_cur_df.columns)

                node_info.append(info)
            else:
                logger.warning(f"Node {node_id} not found for feature info collection")

        return {
            "selected_nodes": selected_node_ids,
            "node_count": len(selected_node_ids),
            "total_features": total_features,
            "node_details": node_info,
            "db_table_name": self.db_table_name,
            "target_column": self.target_col
        }