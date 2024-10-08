class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

class Solution:
    def countPairs(self, root: TreeNode, distance: int) -> int:
        self.result = 0

        def dfs(node):
            if not node:
                return []
            if not node.left and not node.right:
                return [1]  # Distance to itself is 1

            left_distances = dfs(node.left)
            right_distances = dfs(node.right)

            # Count pairs between left and right distances
            for l in left_distances:
                for r in right_distances:
                    if l + r <= distance:
                        self.result += 1

            # Return distances incremented by 1 (distance to parent)
            return [d + 1 for d in left_distances + right_distances if d + 1 <= distance]

        dfs(root)
        return self.result