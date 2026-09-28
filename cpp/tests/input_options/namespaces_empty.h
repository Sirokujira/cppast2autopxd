// Fixture for the "matched" side of --namespace (#61): what selects nothing
// must warn even when the NAME exists. There is no file-level declaration
// here, so `--namespace ::` matches no block -- the file-start header the
// emitter always writes is dropped as empty and must not count. And
// `only_using` holds nothing but a using-directive: the emitter opens a
// block for it, writes nothing into it, drops it -- same rule.
#pragma once

namespace only {
int f();
}  // namespace only

namespace only_using {
using namespace only;
}  // namespace only_using
