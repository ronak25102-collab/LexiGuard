from enum import StrEnum

from pydantic import BaseModel, Field

# 41 CUAD Categories
CUAD_CLAUSE_CATEGORIES = [
    "Document Name", "Parties", "Agreement Date", "Effective Date",
    "Expiration Date", "Renewal Term", "Notice Period To Terminate Renewal",
    "Governing Law", "Most Favored Nation", "Non-Compete", "Exclusivity",
    "No-Solicit Of Customers", "Competitive Restriction Exception",
    "No-Solicit Of Employees", "Non-Disparagement", "Termination For Convenience",
    "Rofr/Rofo/Rofn", "Change Of Control", "Anti-Assignment",
    "Revenue/Profit Sharing", "Price Restrictions", "Minimum Commitment",
    "Volume Restriction", "Ip Ownership Assignment", "Joint Ip Ownership",
    "License Grant", "Non-Transferable License", "Affiliate License-Loss",
    "Unlimited/All-You-Can-Eat-License", "Irrevocable Or Perpetual License",
    "Source Code Escrow", "Post-Termination Services", "Audit Rights",
    "Uncapped Liability", "Cap On Liability", "Liquidated Damages",
    "Warranty Duration", "Insurance", "Covenant Not To Sue",
    "Third Party Beneficiary", "Indemnification"
]


class RelationshipType(StrEnum):
    """Types of cross-references between clauses."""
    REFERENCES = "REFERENCES"
    MODIFIES = "MODIFIES"
    SUPERSEDES = "SUPERSEDES"
    EXCLUDES = "EXCLUDES"


class PartyInfo(BaseModel):
    """A contracting party (company or individual)."""
    name: str = Field(description="Legal name of the party")
    role: str = Field(description="Role in the contract, e.g., 'Buyer', 'Seller', 'Licensor', 'Licensee'")
    jurisdiction: str | None = Field(default=None, description="Jurisdiction of incorporation")


class ClauseInfo(BaseModel):
    """A legal clause within a contract."""
    number: str = Field(description="Clause number, e.g., '3.1', '12.2(a)'")
    title: str = Field(description="Clause title, e.g., 'Termination', 'Non-Compete'")
    text: str = Field(description="Full verbatim text of the clause")
    clause_type: str = Field(description="CUAD category classification")


class LocationInfo(BaseModel):
    """A geographic or jurisdictional location."""
    name: str = Field(description="Location name")
    location_type: str = Field(description="Type: 'state', 'country', 'jurisdiction'")


class CrossReference(BaseModel):
    """A relationship between two clauses."""
    source_clause: str = Field(description="Source clause number")
    target_clause: str = Field(description="Target clause number")
    relationship: str = Field(description="Relationship type: REFERENCES, MODIFIES, SUPERSEDES, EXCLUDES")


class ExtractionData(BaseModel):
    """Data model for LLM extraction (no source_file required)."""
    title: str = Field(default="", description="Title of the contract")
    contract_type: str = Field(default="", description="Type of contract, e.g., NDA, License Agreement")
    effective_date: str | None = Field(default=None, description="Effective date of the contract")
    expiry_date: str | None = Field(default=None, description="Expiry date of the contract")
    governing_law: str | None = Field(default=None, description="Governing law or jurisdiction")
    parties: list[PartyInfo] = Field(default_factory=list)
    clauses: list[ClauseInfo] = Field(default_factory=list)
    locations: list[LocationInfo] = Field(default_factory=list)
    cross_references: list[CrossReference] = Field(default_factory=list)


class ContractData(BaseModel):
    """Complete extracted data from a single contract."""
    source_file: str
    title: str
    contract_type: str
    effective_date: str | None = None
    expiry_date: str | None = None
    governing_law: str | None = None
    parties: list[PartyInfo] = Field(default_factory=list)
    clauses: list[ClauseInfo] = Field(default_factory=list)
    locations: list[LocationInfo] = Field(default_factory=list)
    cross_references: list[CrossReference] = Field(default_factory=list)
