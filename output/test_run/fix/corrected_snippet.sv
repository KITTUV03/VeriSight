    // Sequential output register
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 8'b0;
            carry  <= 1'b0;
            zero   <= 1'b0;
        end else begin
            result <= alu_out[7:0];
            carry  <= alu_out[8];
            zero   <= zero_next;
        end
    end