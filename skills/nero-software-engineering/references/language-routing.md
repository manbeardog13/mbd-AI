# Language and toolchain routing

## Contents

1. Universal protocol
2. Systems and native languages
3. Managed and virtual-machine languages
4. Web and application languages
5. Functional and concurrent languages
6. Data, scientific, query, and configuration languages
7. GPU, graphics, hardware, smart-contract, and formal languages
8. Legacy and uncommon languages
9. Unknown or newly released language protocol

## 1. Universal protocol

For any language:

1. Identify the exact toolchain from repository manifests, lockfiles, CI, and
   version files.
2. Read the build and test entry points before changing code.
3. Recover semantics from tests, callers, interfaces, schemas, and runtime
   behavior.
4. Use the native formatter, parser/compiler, type checker, linter, tests, and
   package/build tools already selected by the repository.
5. Verify version-sensitive claims with official specifications or primary
   toolchain documentation.
6. Test the platform and runtime matrix the repository actually supports.

Do not replace repository-selected tools merely because another tool is more
familiar.

## 2. Systems and native languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| C family | C, Objective-C | undefined behavior, ownership, aliasing, integer conversions, ABI, preprocessor | configured compiler warnings, sanitizer builds, native tests, static analyzer |
| C++ | C++ | lifetime, move/copy behavior, templates, exceptions, ODR, ABI, concurrency | project compiler matrix, sanitizers, clang-tidy if configured, unit/integration tests |
| Rust | Rust | ownership, lifetimes, unsafe blocks, Send/Sync, feature flags, MSRV | `cargo fmt`, `cargo check`, `cargo clippy`, `cargo test`, feature/target matrix |
| Go | Go | goroutine lifetime, channel closure, context cancellation, interfaces, zero values | `gofmt`, `go vet`, `go test`, race detector where appropriate |
| Zig | Zig | allocator ownership, error unions, comptime, target/version churn | pinned `zig build` and tests; official version documentation |
| Swift | Swift | value/reference semantics, optionals, actors, Sendable, ARC, platform availability | SwiftPM/Xcode build and tests for supported targets |
| D/Nim/Crystal | D, Nim, Crystal | GC/manual boundary, macros/templates, version-specific compiler behavior | pinned compiler, formatter/linter if configured, native test runner |
| Ada/SPARK | Ada, SPARK | ranges, contracts, tasking, proof obligations | GNAT build/tests and SPARK proof tools when configured |

Treat headers, FFI declarations, calling conventions, struct layout, alignment,
and linker configuration as part of the public contract.

## 3. Managed and virtual-machine languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| JVM | Java, Kotlin, Scala, Clojure, Groovy | nullability, erasure, reflection, classpath, checked errors, coroutine/future semantics | pinned Gradle/Maven/sbt/Leiningen tasks, compiler, tests, static analysis configured by repo |
| .NET | C#, F#, Visual Basic | nullable context, async/await, disposal, LINQ evaluation, runtime/target framework | `dotnet format` if configured, `dotnet build`, `dotnet test`, analyzers |
| BEAM | Elixir, Erlang | supervision, process mailbox ordering, failure isolation, hot-code assumptions | formatter, compiler, ExUnit/EUnit/Common Test, Dialyzer when configured |
| JVM scripting | JRuby, Jython and embedded JVM DSLs | host-language interop and runtime version coupling | host build plus language-native tests |

Verify runtime and package versions from locked configuration. Do not assume the
latest language behavior applies to an older target framework.

## 4. Web and application languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| JavaScript | JavaScript, JSX | coercion, event loop, module format, runtime/browser differences, prototype behavior | repository package manager, formatter/linter, tests, build, browser/e2e checks |
| TypeScript | TypeScript, TSX | structural typing, unsound assertions, emitted JS/runtime mismatch, module resolution | pinned package manager, `tsc`/build, lint, tests, supported runtime matrix |
| Python | Python | dynamic types, mutation, import paths, sync/async mixing, packaging, supported versions | configured formatter/linter/type checker, `pytest`/native tests, build/install check |
| Ruby | Ruby | monkey patching, metaprogramming, mutation, gem/runtime compatibility | Bundler, configured lint, test framework, packaging check |
| PHP | PHP | weak/strict typing boundaries, magic methods, request lifecycle, extension/runtime variance | Composer, configured analyzer/linter, test suite, supported PHP matrix |
| Dart | Dart, Flutter | null safety, futures/streams, widget lifecycle, generated code | `dart format`, analyzer, tests, Flutter build/integration checks |
| Apple app | Swift, Objective-C | platform lifecycle, entitlements, concurrency, availability | Xcode/SwiftPM build and platform tests |
| Android app | Kotlin, Java | lifecycle, coroutines, threading, SDK/API levels, resources | Gradle checks, unit/instrumented tests, supported API matrix |
| UI components | Vue, Svelte, Astro, templates | compile-time transforms, hydration, reactivity, escaping, accessibility | framework compiler/build, unit/component/e2e and accessibility checks |

For browser code, verify security boundaries, output encoding, accessibility,
responsive behavior, and supported browsers—not only unit tests.

## 5. Functional and concurrent languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| ML | OCaml, Standard ML, F# | algebraic types, exhaustiveness, effects, module boundaries | native build, formatter, compiler warnings, tests |
| Haskell | Haskell | laziness, partial functions, effects, space leaks, typeclass resolution | pinned Cabal/Stack build, warnings, tests, property tests |
| Lisp | Clojure, Common Lisp, Scheme, Racket | macros, dynamic vars, evaluation phase, host/runtime interop | implementation-native build/test and macro-expansion checks |
| Actor/concurrent | Erlang, Elixir, Pony, Akka-based code | ordering, supervision, backpressure, cancellation, partition behavior | concurrency-focused tests, fault injection, native analyzers |

Prefer property-based testing where algebraic invariants matter. Test evaluation
order and resource usage when laziness or macros can hide runtime costs.

## 6. Data, scientific, query, and configuration languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| SQL | SQL dialects, PL/SQL, T-SQL, PL/pgSQL | dialect, NULL/three-valued logic, isolation, locks, migration reversibility, query plans | target database, migration dry run, transaction tests, explain plans with representative data |
| Scientific | R, Julia, MATLAB/Octave, Mathematica | missing values, vectorization, broadcasting, numeric stability, reproducibility | native package/project tests, fixed seeds, tolerance-based numeric checks |
| Shell | Bash, POSIX sh, PowerShell, fish | quoting, word splitting, pipeline errors, platform tools, exit-code propagation | parser/linter if configured, isolated execution, failure-path tests on target shell |
| Data/config | JSON, YAML, TOML, XML, INI, HCL | schema, coercion, duplicate keys, anchors, escaping, environment interpolation | schema validation, parser round-trip, target application validation |
| API/query | GraphQL, OpenAPI, protobuf, Avro, Thrift | compatibility, optionality, field numbering, resolver cost, generated-code drift | schema compiler/linter, compatibility checker, contract tests |
| Build DSL | Make, CMake, Meson, Gradle, Bazel/Starlark, Nix | incremental correctness, quoting, platform/toolchain selection, cache keys | clean and incremental builds, target matrix, reproducibility checks |

Never treat configuration as harmless text. It can carry executable commands,
secrets, deployment policy, and compatibility contracts.

## 7. GPU, graphics, hardware, smart-contract, and formal languages

| Family | Languages | High-risk semantics | Native proof route |
|---|---|---|---|
| GPU/compute | CUDA, HIP, OpenCL, SYCL | memory spaces, synchronization, race conditions, precision, device capability | compiler, device tests, race/profiler tools, CPU/reference comparison |
| Shaders | HLSL, GLSL, WGSL, Metal Shading Language | coordinate spaces, precision, resource binding, undefined derivatives, backend variance | target shader compiler, validation layers, representative render/golden images |
| Hardware | Verilog, SystemVerilog, VHDL, Chisel | clocks/resets, blocking/nonblocking semantics, metastability assumptions, synthesis mismatch | lint, simulation, assertions/formal checks, synthesis timing/resource report |
| Smart contracts | Solidity, Vyper, Move, Rust-based chains | reentrancy, authorization, integer/economic invariants, upgradeability, finality | pinned toolchain, static analyzers, unit/fuzz/invariant tests, fork/testnet simulation |
| Formal/proof | Lean, Coq, Isabelle, Agda, TLA+ | trusted base, theorem assumptions, model scope, extraction mismatch | native checker with no admitted holes, model checking, extracted-code tests |

Treat visual output, device behavior, economic invariants, and proofs as primary
artifacts. A successful compile alone is insufficient.

## 8. Legacy and uncommon languages

For COBOL, Fortran, Pascal/Delphi, Assembly, ABAP, Apex, SAS, Tcl, Prolog, Smalltalk,
RPG, LabVIEW-generated code, domain-specific languages, and proprietary scripting:

1. Identify the exact vendor/runtime/dialect and supported platform.
2. Preserve fixed formats, record layouts, encodings, calling conventions,
   transaction semantics, and external system contracts.
3. Use the repository's compiler/emulator/test harness rather than substituting a
   superficially similar modern dialect.
4. Build characterization tests before modernization.
5. Port behind stable adapters and compare source/target behavior on real fixtures.

## 9. Unknown or newly released language protocol

When the language is absent from this guide or likely changed:

1. Identify the file grammar, official language home, specification, reference
   implementation, package manager, formatter, compiler/interpreter, and tests.
2. Confirm versions from the repository and installed toolchain.
3. Read primary documentation for the exact feature used.
4. Construct the smallest compiling/running example that answers the uncertainty.
5. Apply the universal protocol and record unresolved version or platform risk.

This protocol is how Nero works credibly across languages without pretending
that a static prompt can contain every evolving ecosystem.

