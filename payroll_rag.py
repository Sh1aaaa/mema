import re

class PayrollRAGEngine:
    def __init__(self):
        self.knowledge_base = [
            {
                "topic": "Hourly Rate Calculation",
                "clause": "COA-SECTION-101: Baseline hourly compensation metrics are derived strictly by dividing the verified institutional Daily Rate by 8 operational working hours."
            },
            {
                "topic": "Tardiness Deductions",
                "clause": "COA-SECTION-102: Salary reductions for late attendance are evaluated as: Hourly Rate multiplied by total tardiness duration converted to hours (tardiness_mins / 60). All computations are rounded to two decimal places."
            },
            {
                "topic": "GSIS Contributions",
                "clause": "STATUTORY-GSIS-9: The Government Service Insurance System (GSIS) personal share deduction is fixed at exactly 9.00% of the computed Gross Compensation for all permanent institutional personnel."
            },
            {
                "topic": "PhilHealth Contributions",
                "clause": "STATUTORY-PH-2: Philippine Health Insurance Corporation (PhilHealth) premium contributions are mandated at exactly 2.00% of the calculated Gross Compensation."
            },
            {
                "topic": "Net Pay Protection Floor",
                "clause": "AUDIT-FLOOR-00: In compliance with strict public accounting regulations, net disbursed take-home compensation balances cannot drop below zero. Any ledger resulting in negative balances must be capped at 0.00 for formal audit evaluation."
            },
            {
                "topic": "Salary Adjustments & Discrepancies",
                "clause": "POLICY-REV-01: Employees noting mathematical variance or operational discrepancies outside basic automated calculations must not alter system states. Instead, instruct the individual to 'File a Formal Revision Request' with the Super Admin."
            }
        ]

    def _tokenize(self, text):
        return set(re.findall(r'\b\w+\b', text.lower()))

    def retrieve_relevant_context(self, user_query, top_k=2):
        query_tokens = self._tokenize(user_query)
        scored_clauses = []

        for item in self.knowledge_base:
            clause_tokens = self._tokenize(item["topic"] + " " + item["clause"])
            overlap_score = len(query_tokens.intersection(clause_tokens))
            scored_clauses.append((overlap_score, item["clause"]))

        scored_clauses.sort(key=lambda x: x[0], reverse=True)
        top_matches = [clause for score, clause in scored_clauses[:top_k]]
        return "\n".join(top_matches)