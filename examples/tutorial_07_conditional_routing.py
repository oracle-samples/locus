"""
Tutorial 07: Conditional Routing

This tutorial covers:
- Dynamic routing with conditional edges
- Router functions
- Multi-way branching
- Combining conditions

Prerequisites: Tutorial 06 (Basic Graph)
Difficulty: Intermediate
"""

import asyncio

from locus.multiagent import END, START, StateGraph


# =============================================================================
# Part 1: Simple Binary Routing
# =============================================================================


async def example_binary_routing():
    """Route to one of two paths based on a condition."""
    print("=== Part 1: Binary Routing ===\n")

    graph = StateGraph()

    async def check_age(inputs):
        age = inputs.get("age", 0)
        return {"age": age, "is_adult": age >= 18}

    async def adult_path(inputs):
        return {"message": "Welcome! You have full access."}

    async def minor_path(inputs):
        return {"message": "Welcome! Parental guidance required."}

    graph.add_node("check", check_age)
    graph.add_node("adult", adult_path)
    graph.add_node("minor", minor_path)

    graph.add_edge(START, "check")

    # Conditional routing based on is_adult
    graph.add_conditional_edges(
        "check",
        # Router function: returns the target node name
        lambda state: "adult" if state.get("is_adult") else "minor",
        # Optional: map router output to actual node names
        {"adult": "adult", "minor": "minor"},
    )

    graph.add_edge("adult", END)
    graph.add_edge("minor", END)

    # Test both paths
    for age in [25, 15]:
        result = await graph.execute({"age": age})
        print(f"Age {age}: {result.final_state.get('message')}")
    print()


# =============================================================================
# Part 2: Multi-Way Routing
# =============================================================================


async def example_multiway_routing():
    """Route to multiple possible paths."""
    print("=== Part 2: Multi-Way Routing ===\n")

    graph = StateGraph()

    async def classify_ticket(inputs):
        priority = inputs.get("priority", "low")
        return {"priority": priority}

    async def handle_critical(inputs):
        return {"response": "CRITICAL: Immediate escalation!", "sla": "1 hour"}

    async def handle_high(inputs):
        return {"response": "HIGH: Priority queue", "sla": "4 hours"}

    async def handle_normal(inputs):
        return {"response": "NORMAL: Standard queue", "sla": "24 hours"}

    async def handle_low(inputs):
        return {"response": "LOW: Backlog", "sla": "1 week"}

    graph.add_node("classify", classify_ticket)
    graph.add_node("critical", handle_critical)
    graph.add_node("high", handle_high)
    graph.add_node("normal", handle_normal)
    graph.add_node("low", handle_low)

    graph.add_edge(START, "classify")

    # Router with multiple outcomes
    def priority_router(state):
        priority = state.get("priority", "low")
        if priority == "critical":  # noqa: SIM116 — explicit if/elif is clearer in the tutorial
            return "critical"
        elif priority == "high":
            return "high"
        elif priority == "medium":
            return "normal"
        else:
            return "low"

    graph.add_conditional_edges("classify", priority_router)

    graph.add_edge("critical", END)
    graph.add_edge("high", END)
    graph.add_edge("normal", END)
    graph.add_edge("low", END)

    # Test different priorities
    for priority in ["critical", "high", "medium", "low"]:
        result = await graph.execute({"priority": priority})
        print(f"{priority.upper()}: {result.final_state.get('response')}")
    print()


# =============================================================================
# Part 3: Chained Conditions
# =============================================================================


async def example_chained_conditions():
    """Multiple conditional routing steps."""
    print("=== Part 3: Chained Conditions ===\n")

    graph = StateGraph()

    async def authenticate(inputs):
        token = inputs.get("token", "")
        is_valid = token == "secret123"  # noqa: S105 — tutorial literal, not a real secret
        return {"authenticated": is_valid}

    async def check_permissions(inputs):
        role = inputs.get("role", "guest")
        return {"is_admin": role == "admin"}

    async def admin_action(inputs):
        return {"result": "Admin operation completed"}

    async def user_action(inputs):
        return {"result": "User operation completed"}

    async def access_denied(inputs):
        return {"result": "Access denied - invalid token"}

    graph.add_node("auth", authenticate)
    graph.add_node("permissions", check_permissions)
    graph.add_node("admin", admin_action)
    graph.add_node("user", user_action)
    graph.add_node("denied", access_denied)

    graph.add_edge(START, "auth")

    # First condition: authenticated?
    graph.add_conditional_edges(
        "auth", lambda s: "permissions" if s.get("authenticated") else "denied"
    )

    # Second condition: admin?
    graph.add_conditional_edges("permissions", lambda s: "admin" if s.get("is_admin") else "user")

    graph.add_edge("admin", END)
    graph.add_edge("user", END)
    graph.add_edge("denied", END)

    # Test scenarios
    test_cases = [
        {"token": "wrong", "role": "admin"},  # Denied
        {"token": "secret123", "role": "user"},  # User path
        {"token": "secret123", "role": "admin"},  # Admin path
    ]

    for case in test_cases:
        result = await graph.execute(case)
        print(f"Token: {case['token'][:6]}..., Role: {case['role']}")
        print(f"  -> {result.final_state.get('result')}")
    print()


# =============================================================================
# Part 4: Routing with Default
# =============================================================================


async def example_default_route():
    """Handle unexpected values with a default route."""
    print("=== Part 4: Default Route ===\n")

    graph = StateGraph()

    async def categorize(inputs):
        category = inputs.get("category", "unknown")
        return {"category": category}

    async def handle_tech(inputs):
        return {"handler": "Tech Support Team"}

    async def handle_billing(inputs):
        return {"handler": "Billing Department"}

    async def handle_sales(inputs):
        return {"handler": "Sales Team"}

    async def handle_other(inputs):
        return {"handler": "General Support"}

    graph.add_node("categorize", categorize)
    graph.add_node("tech", handle_tech)
    graph.add_node("billing", handle_billing)
    graph.add_node("sales", handle_sales)
    graph.add_node("other", handle_other)

    graph.add_edge(START, "categorize")

    # Conditional edges with explicit mapping and default
    graph.add_conditional_edges(
        "categorize",
        lambda s: s.get("category", "other"),
        targets={
            "tech": "tech",
            "billing": "billing",
            "sales": "sales",
        },
        default="other",  # Fallback for unknown categories
    )

    graph.add_edge("tech", END)
    graph.add_edge("billing", END)
    graph.add_edge("sales", END)
    graph.add_edge("other", END)

    # Test including unknown category
    for category in ["tech", "billing", "returns", "xyz"]:
        result = await graph.execute({"category": category})
        print(f"Category '{category}': {result.final_state.get('handler')}")
    print()


# =============================================================================
# Part 5: Complex Routing Logic
# =============================================================================


async def example_complex_routing():
    """Combine multiple factors in routing decision."""
    print("=== Part 5: Complex Routing ===\n")

    graph = StateGraph()

    async def evaluate_order(inputs):
        amount = inputs.get("amount", 0)
        customer_type = inputs.get("customer_type", "regular")
        items = inputs.get("items", 1)

        return {
            "amount": amount,
            "customer_type": customer_type,
            "items": items,
            "is_bulk": items > 10,
            "is_vip": customer_type == "vip",
            "is_large": amount > 1000,
        }

    async def express_processing(inputs):
        return {"processing": "EXPRESS", "eta": "Same day"}

    async def priority_processing(inputs):
        return {"processing": "PRIORITY", "eta": "1-2 days"}

    async def standard_processing(inputs):
        return {"processing": "STANDARD", "eta": "3-5 days"}

    graph.add_node("evaluate", evaluate_order)
    graph.add_node("express", express_processing)
    graph.add_node("priority", priority_processing)
    graph.add_node("standard", standard_processing)

    graph.add_edge(START, "evaluate")

    # Complex routing logic
    def order_router(state):
        is_vip = state.get("is_vip", False)
        is_large = state.get("is_large", False)
        is_bulk = state.get("is_bulk", False)

        # VIP with large order -> express
        if is_vip and is_large:
            return "express"
        # VIP or large order -> priority
        elif is_vip or is_large or is_bulk:
            return "priority"
        # Everyone else -> standard
        else:
            return "standard"

    graph.add_conditional_edges("evaluate", order_router)

    graph.add_edge("express", END)
    graph.add_edge("priority", END)
    graph.add_edge("standard", END)

    # Test scenarios
    test_cases = [
        {"amount": 500, "customer_type": "regular", "items": 2},
        {"amount": 500, "customer_type": "vip", "items": 2},
        {"amount": 2000, "customer_type": "regular", "items": 2},
        {"amount": 2000, "customer_type": "vip", "items": 20},
    ]

    for case in test_cases:
        result = await graph.execute(case)
        print(f"Order: ${case['amount']}, {case['customer_type']}, {case['items']} items")
        print(f"  -> {result.final_state.get('processing')}: {result.final_state.get('eta')}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 07: Conditional Routing")
    print("=" * 60)
    print()

    await example_binary_routing()
    await example_multiway_routing()
    await example_chained_conditions()
    await example_default_route()
    await example_complex_routing()

    print("=" * 60)
    print("Next: Tutorial 08 - State Reducers")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
