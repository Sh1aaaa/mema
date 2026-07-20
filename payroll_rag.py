import re


class PayrollRAGEngine:
    def __init__(self):
        self.knowledge_base = [
            {
                "topic": "Hourly Rate Calculation",
                "clause": (
                    "COA-SECTION-101: Baseline hourly compensation "
                    "metrics are derived strictly by dividing the "
                    "verified institutional Daily Rate by 8 "
                    "operational working hours."
                ),
            },
            {
                "topic": "Tardiness Deductions",
                "clause": (
                    "COA-SECTION-102: Salary reductions for late "
                    "attendance are evaluated as the Hourly Rate "
                    "multiplied by total tardiness duration converted "
                    "to hours using tardiness_mins divided by 60. "
                    "All computations are rounded to two decimal places."
                ),
            },
            {
                "topic": "GSIS Contributions",
                "clause": (
                    "STATUTORY-GSIS-9: The Government Service "
                    "Insurance System personal-share deduction is "
                    "fixed at exactly 9.00% of computed Gross "
                    "Compensation for permanent institutional personnel."
                ),
            },
            {
                "topic": "PhilHealth Contributions",
                "clause": (
                    "STATUTORY-PH-2: Philippine Health Insurance "
                    "Corporation premium contributions are calculated "
                    "at exactly 2.00% of Gross Compensation."
                ),
            },
            {
                "topic": "Net Pay Protection Floor",
                "clause": (
                    "AUDIT-FLOOR-00: Net take-home compensation "
                    "cannot drop below zero. Any ledger resulting "
                    "in a negative balance must be capped at 0.00."
                ),
            },
            {
                "topic": "Salary Adjustments and Discrepancies",
                "clause": (
                    "POLICY-REV-01: Employees reporting mathematical "
                    "variance or operational discrepancies must not "
                    "alter payroll system records. They must "
                    "'File a Formal Revision Request' "
                    "with the Super Admin."
                ),
            },
        ]

    def _tokenize(self, text):
        """
        Converts text into a unique set of lowercase word tokens.
        """

        return set(
            re.findall(
                r"\b\w+\b",
                str(text).lower(),
            )
        )

    def retrieve_relevant_context(
        self,
        user_query,
        top_k=2,
    ):
        """
        Retrieves the clauses with the highest word overlap
        with the employee's question.
        """

        query_tokens = self._tokenize(
            user_query
        )

        if not query_tokens:
            return (
                "No relevant regulatory clause "
                "was found for the empty query."
            )

        try:
            top_k = int(top_k)

        except (TypeError, ValueError):
            top_k = 2

        top_k = max(
            1,
            min(
                top_k,
                len(self.knowledge_base),
            ),
        )

        scored_clauses = []

        for index, item in enumerate(
            self.knowledge_base
        ):
            combined_text = (
                f"{item['topic']} "
                f"{item['clause']}"
            )

            clause_tokens = self._tokenize(
                combined_text
            )

            overlap_score = len(
                query_tokens.intersection(
                    clause_tokens
                )
            )

            scored_clauses.append(
                (
                    overlap_score,
                    index,
                    item["topic"],
                    item["clause"],
                )
            )

        scored_clauses.sort(
            key=lambda result: (
                result[0],
                -result[1],
            ),
            reverse=True,
        )

        positive_matches = [
            result
            for result in scored_clauses
            if result[0] > 0
        ]

        selected_matches = (
            positive_matches[:top_k]
            if positive_matches
            else scored_clauses[:top_k]
        )

        formatted_matches = []

        for (
            score,
            _,
            topic,
            clause,
        ) in selected_matches:
            formatted_matches.append(
                f"Topic: {topic}\n"
                f"Clause: {clause}"
            )

        return "\n\n".join(
            formatted_matches
        )
