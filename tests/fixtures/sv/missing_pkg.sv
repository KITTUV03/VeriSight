// Syntactically valid, but imports a package that is not provided.
// This must be reported as a MISSING DEPENDENCY, not a syntax error.
module uses_missing_pkg (
    input  logic clk,
    output absent_pkg::word_t out
);
    import absent_pkg::*;
    assign out = make_word();
endmodule
