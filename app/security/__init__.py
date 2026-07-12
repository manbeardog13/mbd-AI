"""The security layer: risk classification, confirmation, and the project jail.

Built *before* the powerful capabilities depend on it (ADR-0005), so no unsafe
path can exist first. Everything an agent does flows through `gate.authorize`.
"""
