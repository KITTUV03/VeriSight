// SVA properties with temporal operators and implication (|-> and |=>).
module sva_props (
    input  logic clk,
    input  logic rst_n,
    input  logic req,
    output logic ack
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) ack <= 1'b0;
        else        ack <= req;
    end

    // Overlapping implication
    property p_req_ack;
        @(posedge clk) disable iff (!rst_n)
        req |-> ##1 ack;
    endproperty

    // Non-overlapping implication with a sequence
    sequence s_two_reqs;
        req ##1 req;
    endsequence

    property p_seq;
        @(posedge clk) disable iff (!rst_n)
        s_two_reqs |=> ack;
    endproperty

    a_req_ack: assert property (p_req_ack);
    a_seq:     assert property (p_seq);
    c_req:     cover property (@(posedge clk) req);
endmodule
