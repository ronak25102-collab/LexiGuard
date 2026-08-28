# Neo4j Graph Schema — LexiGuard

## Node Types

### Contract
The central node representing a legal agreement.

| Property | Type | Description |
|----------|------|-------------|
| `id` | String | Unique identifier (hash of filename) |
| `title` | String | Contract title |
| `type` | String | Contract category (NDA, License, Service, etc.) |
| `effective_date` | String | When the contract takes effect |
| `expiry_date` | String | When the contract expires |
| `governing_law` | String | Governing jurisdiction |
| `source_file` | String | Original PDF filename |

### Party
A contracting entity (company or individual).

| Property | Type | Description |
|----------|------|-------------|
| `name` | String | Legal name of the party |
| `role` | String | Role: Buyer, Seller, Licensor, Licensee, etc. |
| `jurisdiction` | String | Jurisdiction of incorporation |

### Clause
A specific legal provision within a contract.

| Property | Type | Description |
|----------|------|-------------|
| `id` | String | Unique ID (contract_id + clause_number) |
| `number` | String | Clause number (e.g., "3.1", "12.2(a)") |
| `title` | String | Clause heading |
| `text` | String | Full verbatim text |
| `type` | String | One of 41 CUAD categories |

### Location
A geographic or jurisdictional entity.

| Property | Type | Description |
|----------|------|-------------|
| `name` | String | Location name |
| `type` | String | state, country, or jurisdiction |

---

## Relationship Types

### Contract → Party
```cypher
(c:Contract)-[:HAS_PARTY {role: "Buyer"}]->(p:Party)
```

### Contract → Clause
```cypher
(c:Contract)-[:CONTAINS_CLAUSE]->(cl:Clause)
```

### Contract → Location
```cypher
(c:Contract)-[:GOVERNED_BY]->(l:Location)
```

### Party → Location
```cypher
(p:Party)-[:INCORPORATED_IN]->(l:Location)
```

### Clause → Clause (Cross-References)
These are the critical relationships that enable multi-hop reasoning:

```cypher
-- Clause A references Clause B
(cl1:Clause)-[:REFERENCES]->(cl2:Clause)

-- Amendment: Clause A modifies the terms of Clause B
(cl1:Clause)-[:MODIFIES]->(cl2:Clause)

-- Override: Clause A supersedes and replaces Clause B
(cl1:Clause)-[:SUPERSEDES]->(cl2:Clause)

-- Exclusion: Clause A excludes the applicability of Clause B
(cl1:Clause)-[:EXCLUDES]->(cl2:Clause)
```

---

## Sample Cypher Queries

### Find all parties in a contract
```cypher
MATCH (c:Contract {title: "Master Services Agreement"})-[:HAS_PARTY]->(p:Party)
RETURN p.name, p.role, p.jurisdiction
```

### Find clauses modified by other clauses
```cypher
MATCH (cl1:Clause)-[:MODIFIES]->(cl2:Clause)
RETURN cl1.number AS modifier, cl1.title AS modifier_title,
       cl2.number AS modified, cl2.title AS modified_title
```

### Find termination clauses across all contracts
```cypher
MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(cl:Clause)
WHERE cl.type = "Termination For Convenience"
RETURN c.title, cl.number, cl.text
```

### Multi-hop: Find parties with non-compete obligations in Delaware
```cypher
MATCH (p:Party)-[:INCORPORATED_IN]->(l:Location {name: "Delaware"})
MATCH (c:Contract)-[:HAS_PARTY]->(p)
MATCH (c)-[:CONTAINS_CLAUSE]->(cl:Clause {type: "Non-Compete"})
RETURN p.name, c.title, cl.text
```

### Find clauses that are superseded
```cypher
MATCH (new:Clause)-[:SUPERSEDES]->(old:Clause)
MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(old)
RETURN c.title, old.number AS superseded_clause,
       new.number AS superseding_clause, new.text
```

---

## CUAD Clause Categories (41)

The 41 categories from the Contract Understanding Atticus Dataset:

1. Document Name
2. Parties
3. Agreement Date
4. Effective Date
5. Expiration Date
6. Renewal Term
7. Notice Period To Terminate Renewal
8. Governing Law
9. Most Favored Nation
10. Non-Compete
11. Exclusivity
12. No-Solicit Of Customers
13. Competitive Restriction Exception
14. No-Solicit Of Employees
15. Non-Disparagement
16. Termination For Convenience
17. Rofr/Rofo/Rofn
18. Change Of Control
19. Anti-Assignment
20. Revenue/Profit Sharing
21. Price Restrictions
22. Minimum Commitment
23. Volume Restriction
24. Ip Ownership Assignment
25. Joint Ip Ownership
26. License Grant
27. Non-Transferable License
28. Affiliate License-Loss
29. Unlimited/All-You-Can-Eat-License
30. Irrevocable Or Perpetual License
31. Source Code Escrow
32. Post-Termination Services
33. Audit Rights
34. Uncapped Liability
35. Cap On Liability
36. Liquidated Damages
37. Warranty Duration
38. Insurance
39. Covenant Not To Sue
40. Third Party Beneficiary
41. Indemnification
