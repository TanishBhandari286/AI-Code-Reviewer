import os
import re
import hashlib
from typing import Literal
from typing import Tuple

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

# Placeholder for OpenAI client setup. Using environment variable OPENAI_API_KEY
# The real GPT-5 model name may differ; placeholder used per request.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5")
# Control provider explicitly. Default to fast heuristic to avoid external calls unless opted in.
AI_PROVIDER = os.getenv("AI_PROVIDER", "heuristic").lower()

Classification = Literal["development", "DSA"]


def classify_file_and_feedback(path: str, content: str) -> tuple[Classification, str]:
    """
    Classify file content and return feedback text according to the rules.
    For now, a deterministic heuristic stub is used to keep the project runnable
    without external API calls. Replace with OpenAI API integration.
    """
    # Try OpenAI only if explicitly enabled
    if AI_PROVIDER == "openai" and OPENAI_API_KEY and OpenAI is not None:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = (
                "You are a senior code reviewer. Classify the code file as either 'development' or 'DSA' (data structures & algorithms). "
                "Return a strict JSON object with keys: classification (development|DSA) and feedback (string).\n\n"
                f"File path: {path}\n\n"
                f"Content:\n{content[:8000]}\n\n"  # cap input for safety
                "Rules for feedback: If DSA, provide three interview questions (easy, medium, hard). If development, provide short, actionable notes on repetition, best practices, security, stack choice, suggestions."
            )
            resp = client.responses.create(
                model=MODEL_NAME,
                input=prompt,
                temperature=0.2,
            )
            text = resp.output_text  # unified accessor
            # naive json extraction
            import json, re
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                data = json.loads(match.group(0))
                cls = str(data.get("classification", "development")).strip()
                fb = str(data.get("feedback", "")).strip()
                classification: Classification = "DSA" if cls.lower().startswith("dsa") else "development"
                return classification, fb
        except Exception:
            pass

    lower = content.lower()
    is_dsa = _looks_like_dsa(path, content)

    if is_dsa:
        classification: Classification = "DSA"
        feedback = _dsa_feedback(path, content)
    else:
        classification = "development"
        feedback = _dev_feedback(path, content)

    return classification, feedback


def _looks_like_dsa(path: str, content: str) -> bool:
    lower = content.lower()
    path_l = path.lower()
    topic_hints = [
        "array", "linkedlist", "linked list", "tree", "graph", "stack", "queue", "heap",
        "trie", "dp", "dynamic", "recursion", "backtrack", "bfs", "dfs", "dijkstra",
        "bellman", "kruskal", "prim", "two pointers", "two_pointers", "sliding", "window",
        "binarysearch", "binary search", "sort", "merge", "quick", "hash", "bit", "matrix",
    ]
    if any(k in lower for k in topic_hints) or any(k in path_l for k in topic_hints):
        return True
    # Lightweight structural hint: short, single-file algorithmic snippet
    if ("import" not in lower and "require(" not in lower and len(content.splitlines()) < 250):
        return True
    return False


def _comment_prefix(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".py"}:
        return "#"
    if ext in {".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".go", ".rs"}:
        return "//"
    return "//"


def _seed_from_path(path: str) -> int:
    h = hashlib.md5(path.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _detect_topic(path: str, content: str) -> str:
    path_l = path.lower()
    text = (path + "\n" + content).lower()
    # Ordered by specificity
    rules = [
        ("Linked List", ["linkedlist", "linked list", "ll", "node.next", "head", "tail"]),
        ("Binary Search", ["binarysearch", "binary search", "low =", "high =", "mid", "low<=high", "while (low", "while(low"]),
        ("Two Pointers", ["two pointers", "two_pointers", "i++", "j--", "i<j", "left", "right"]),
        ("Sliding Window", ["sliding window", "window", "while (right", "while(right", "while (left", "while(left"]),
        ("Recursion", ["recursion", "recur", "recursive", "return f(", "return fact(", "return fib("]),
        ("Dynamic Programming", ["dp[", "dp.", "memo", "tabulation", "bottom-up", "top-down"]),
        ("Backtracking", ["backtrack", "choose", "unchoose", "path.pop", "visited.remove"]),
        ("Graph Traversal", ["dfs", "bfs", "adj", "adjacency", "queue.push", "stack.push", "visited["]),
        ("Shortest Path", ["dijkstra", "bellman", "floyd", "spfa"]),
        ("Tree", ["tree", "bst", "inorder", "preorder", "postorder", "left", "right", "root"]),
        ("Sorting", ["merge sort", "quicksort", "partition", "pivot", "merge("]),
        ("Stack/Queue", ["stack", "queue", "push", "pop", "enqueue", "dequeue"]),
        ("Heap/Priority Queue", ["heap", "priority queue", "heapify", "sift", "bubble up", "downheap"]),
        ("Greedy", ["greedy", "sort", "take if", "ratio"]),
        ("Bit Manipulation", ["bit", "mask", "<<", ">>", "&", "^", "|", "lowbit"]),
        ("Hashing", ["map", "hash", "object[", "set(", "new Map("]),
        ("Matrix", ["matrix", "grid", "rows", "cols", "m*n"]),
    ]
    for topic, keys in rules:
        if any(k in path_l or k in text for k in keys):
            return topic
    return "General DSA"


def _extract_fn_names(content: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r"function\s+([A-Za-z_]\w*)", content):
        names.append(m.group(1))
    for m in re.finditer(r"const\s+([A-Za-z_]\w*)\s*=\s*\((.*?)\)\s*=>", content):
        names.append(m.group(1))
    for m in re.finditer(r"def\s+([A-Za-z_]\w*)\s*\(", content):
        names.append(m.group(1))
    # unique preserve order
    seen = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered[:3]


def _complexity_hints(content: str) -> str:
    loops = len(re.findall(r"\bfor\b", content))
    nested = len(re.findall(r"for[^{]*\{[\s\S]*for", content))
    rec = False
    fn_names = _extract_fn_names(content)
    for n in fn_names:
        if re.search(rf"\b{re.escape(n)}\s*\(", content.split(n, 1)[-1]):
            rec = True
            break
    hints = []
    if rec:
        hints.append("uses recursion (watch stack depth)")
    if nested >= 1:
        hints.append("has nested loops (likely O(n^2) or worse)")
    elif loops >= 1:
        hints.append("iterative loop(s) present (baseline O(n))")
    return ", ".join(hints) if hints else "no obvious hotspots detected"


def _dsa_feedback(path: str, content: str) -> str:
    topic = _detect_topic(path, content)
    seed = _seed_from_path(path)  # ensures per-file variety but deterministic
    prefix = _comment_prefix(path)
    fns = _extract_fn_names(content)
    fn_label = f" (e.g., {', '.join(fns)})" if fns else ""
    cx = _complexity_hints(content)

    variants: dict[str, list[tuple[str, str, str]]] = {
        "Binary Search": [
            (
                "Explain binary search and its invariants. When does it fail?",
                "Search in a rotated sorted array in O(log n); outline pivot detection vs. modified BS.",
                "Find median of two sorted arrays in O(log(min(m,n))). Describe partition logic.",
            ),
            (
                "Given a sorted array with duplicates, find first and last occurrence of a target.",
                "Peak element in a mountain array. Why two pointers won't work as cleanly?",
                "K-th smallest pair distance using BS on answer; justify monotonic predicate.",
            ),
        ],
        "Two Pointers": [
            (
                "Left/right pointer pattern: when is it preferable to hashing?",
                "3Sum (unique triplets). How do you avoid duplicates efficiently?",
                "Minimum window substring vs. sliding window with counts; correctness proof.",
            ),
            (
                "Move zeros to the end in-place while keeping order.",
                "Container With Most Water: why pointers meet-in-the-middle works.",
                "Trap Rain Water in O(n) with two pointers; derive left/right max logic.",
            ),
        ],
        "Sliding Window": [
            (
                "What makes a problem amenable to sliding window?",
                "Longest substring without repeating characters; time complexity tradeoffs.",
                "Smallest subarray with sum ≥ K with negatives present—why naive window fails.",
            ),
            (
                "Max sum subarray of size K vs. variable window—compare patterns.",
                "Anagrams in a string via window with freq maps; pitfalls.",
                "At most K distinct characters; extend to exactly K using inclusion–exclusion.",
            ),
        ],
        "Recursion": [
            (
                "Tail vs. non-tail recursion; when does it matter in JS/Python?",
                "Generate n-th Fibonacci efficiently—memo vs. tabulation.",
                "Design a recursion to generate combinations/permutations and analyze complexity.",
            ),
            (
                "Base case design: common mistakes and consequences.",
                "Serialize/deserialize a tree recursively; handle nulls well.",
                "Solve N-Queens via backtracking; prune aggressively and argue correctness.",
            ),
        ],
        "Dynamic Programming": [
            (
                "Top-down vs. bottom-up DP—space/time tradeoffs.",
                "Longest Increasing Subsequence: O(n log n) patience sorting idea.",
                "Knuth/Yao or Divide&Conquer DP optimization—when applicable and why.",
            ),
            (
                "Coin Change variants—unbounded vs. 0/1; state definition pitfalls.",
                "Edit distance: state and transitions; reconstruct path.",
                "Tree DP: rerooting technique outline and complexity.",
            ),
        ],
        "Graph Traversal": [
            (
                "BFS vs. DFS—choose based on what property?",
                "Cycle detection in directed graph; color marking vs. stack-based.",
                "Topological sorting—Kahn vs. DFS; prove correctness.",
            ),
            (
                "Connected components count and applications.",
                "Shortest path on unweighted graphs; multi-source BFS.",
                "Bridges and articulation points (Tarjan); real-world uses.",
            ),
        ],
        "Shortest Path": [
            (
                "Dijkstra preconditions; where does it break?",
                "Bellman–Ford: detect negative cycles and report one.",
                "0-1 BFS and Dial's algorithm; when they outperform heap-based Dijkstra.",
            ),
            (
                "Floyd–Warshall basics and optimizations.",
                "Kruskal vs. Prim MST; DSU optimizations.",
                "A* search heuristics—admissibility and consistency.",
            ),
        ],
        "Tree": [
            (
                "Inorder/preorder/postorder—when to use each?",
                "Validate BST with bounds; common bug patterns.",
                "Lowest Common Ancestor variants; binary lifting idea.",
            ),
            (
                "Diameter of a tree in O(n).",
                "Serialize/deserialize a binary tree; choose format.",
                "Segment tree or Fenwick overview; range queries and updates.",
            ),
        ],
        "Sorting": [
            (
                "Stable vs. unstable sorts—why it matters.",
                "Quickselect expected complexity and pivot strategy.",
                "External sorting for huge datasets; I/O considerations.",
            ),
            (
                "Merge sort walk-through and space complexity.",
                "Three-way partitioning quicksort; handling duplicates well.",
                "Order statistics with heaps; compare to selection algorithms.",
            ),
        ],
        "Linked List": [
            (
                "Fast/slow pointers uses (middle, cycle detect).",
                "Reverse k-group nodes; in-place pointer manipulation.",
                "Copy list with random pointer; O(n) time/O(1) extra trick.",
            ),
            (
                "Detect and remove cycle (Floyd) and find cycle start.",
                "Merge two sorted lists; iterative vs. recursive tradeoffs.",
                "LRU cache with list+hash; operations and complexity.",
            ),
        ],
        "Stack/Queue": [
            (
                "Evaluate RPN with a stack—edge cases.",
                "Monotonic stack for next-greater element; correctness.",
                "Queue via two stacks—amortized analysis.",
            ),
            (
                "Min stack design (track current min).",
                "Sliding window maximum with deque; complexity.",
                "Circular queue design; full vs. empty detection.",
            ),
        ],
        "Heap/Priority Queue": [
            (
                "Binary heap invariants.",
                "Merge k sorted lists/arrays with a heap; complexity.",
                "Median of a data stream via two heaps; balancing.",
            ),
            (
                "Heap sort vs. quicksort; practical tradeoffs.",
                "Top-K frequent elements; compare heap vs. bucket sort.",
                "Dary heaps and Fibonacci heaps—when worth it?",
            ),
        ],
        "Greedy": [
            (
                "Greedy-choice property and matroid intuition.",
                "Activity selection and interval scheduling; proofs.",
                "Huffman coding: why optimal?",
            ),
            (
                "Fractional knapsack vs. 0/1; where greedy fails.",
                "Partition labels; why sorting is key.",
                "Gas station problem; correctness argument.",
            ),
        ],
        "Bit Manipulation": [
            (
                "Bitwise basics and typical pitfalls in JS.",
                "Single number (xor) and variants; limits of bit tricks.",
                "Bitmask DP overview; subset enumeration patterns.",
            ),
            (
                "Count set bits; Brian Kernighan vs. builtin.",
                "Reverse bits and why sign matters in JS.",
                "Find two unique numbers where others twice—derive.",
            ),
        ],
        "Hashing": [
            (
                "Hash map/set complexity guarantees.",
                "Group anagrams via signature; collision handling.",
                "Rabin–Karp rolling hash; collision probability.",
            ),
            (
                "Two-sum variants; dedup strategy.",
                "Longest substring with at most K distinct; map maintenance.",
                "Consistent hashing idea and use cases.",
            ),
        ],
        "Matrix": [
            (
                "Spiral traversal pitfalls.",
                "Search in a sorted matrix (binary search on rows/cols).",
                "Rotate matrix in-place; indexing arithmetic.",
            ),
            (
                "Num islands (DFS/BFS on grid).",
                "Prefix sums for submatrix queries.",
                "DP on grids with obstacles; path counting variants.",
            ),
        ],
        "General DSA": [
            (
                "Time/space complexity of the main routine{fn_label}.",
                "Refactor for readability: name helpers, reduce nesting.",
                "Edge-case audit: empty inputs, large n, negative/zero values.",
            ),
            (
                "Document pre/post-conditions{fn_label}.",
                "Property-based test ideas for corner cases.",
                "Parallelization potential and constraints.",
            ),
        ],
    }

    pool = variants.get(topic, variants["General DSA"])
    idx = seed % len(pool)
    easy, medium, hard = pool[idx]

    lines = [
        f"{prefix} DSA Review ({topic})",
        f"{prefix} Complexity hints: {cx}",
        f"{prefix} Easy: {easy}",
        f"{prefix} Medium: {medium}",
        f"{prefix} Hard: {hard}",
    ]
    return "\n".join(lines) + "\n"


def _dev_feedback(path: str, content: str) -> str:
    prefix = _comment_prefix(path)
    js_like = os.path.splitext(path)[1].lower() in {".js", ".ts", ".tsx", ".jsx"}
    notes = [
        "Prefer constants for magic numbers and strings.",
        "Factor shared logic into helpers to keep functions small.",
        "Add brief docstring/comments for non-obvious branches.",
    ]
    if js_like:
        notes.extend([
            "Use const/let over var; prefer strict equality (===).",
            "Avoid implicit globals; enable ESLint and Prettier.",
            "Consider JSDoc/TypeScript annotations for better tooling.",
        ])
    else:
        notes.extend([
            "Add type hints and use a linter/formatter (ruff/black).",
            "Replace prints with structured logging.",
        ])
    lines = [f"{prefix} Development Review"] + [f"{prefix} - {n}" for n in notes]
    return "\n".join(lines) + "\n"
