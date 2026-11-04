// PL side of the seqlock contract: commit data and sequence number in ONE clock cycle.
// (taken from the pattern used in imu_reader.v)
reg [15:0] seq;
reg [31:0] yaw_out, ts_out;
always @(posedge clk) begin
    if (!rst_n) begin seq <= 16'd0; yaw_out <= 32'd0; ts_out <= 32'd0; end
    else if (sample_done) begin       // everything below changes together
        yaw_out <= yaw_next;
        ts_out  <= ts_next;
        seq     <= seq + 16'd1;
    end
end
