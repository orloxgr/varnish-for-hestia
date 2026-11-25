# Coordinated functional acceptance

The qualified combination is Hestia **0.24.13**, Webuzo **0.13.21** and WordPress
UltraCache **dev.1381**. The adapters share the same production native sources.
This document is the public summary of retained qualification evidence; it does
not expose customer identifiers, browser cookies or private lab records.

## What the evidence establishes

- Generated Hestia VCL and its matching native Varnish 9.1 module passed five
  focused HTTP tests with no skips. They cover signed dynamic requests,
  Basic/older-producer preservation, rejection of retired controls, independent
  private cart and anonymous nonce composition, and real cached-body MISS/refill
  followed by reuse. Their signed application producer is explicitly mocked.
- Shared Webuzo native fixtures passed 57 targeted tests. Separate actual
  WordPress/browser tests on Webuzo exercised independent first visits after
  normal Warm, public variants, separate cart/wishlist owners, complete HTML
  delivery with zero backend/PHP calls, actual body MISS then reuse, provider
  mutations and natural session expiration.
- Real WordPress issuer/verifier checks covered login/logout, revoked sessions,
  invalid cross-session nonces, valid actions and nonce aging. Browser evidence
  includes JavaScript on/off and retained visitor cookies. Standalone application
  operation was exercised separately from Varnish.
- Failures remained observable: an actual template failure made normal Warm fail,
  and removing the fault restored a complete reusable response. Historical failed
  checkpoints were retained as failures, not relabelled successful.

## Boundaries

The WordPress/browser evidence is not a Hestia live-deployment claim. The Hestia
tests qualify its adapter with a mock producer; they do not independently repeat
the complete WordPress/browser matrix. This work compares the implementation
against LiteSpeed source/documentation; it is not a LiteSpeed Enterprise server
benchmark or a guarantee for arbitrary plugins.

Current invalidation follows actual provider/content events and dependencies.
Retired whole-application holds, execution-drain RPCs and identity census are not
current admission requirements. See [the Hestia native test contract](../tests/README-1047.md)
for the exact replacement coverage and fixture boundaries.
