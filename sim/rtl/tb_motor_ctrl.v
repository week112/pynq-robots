`timescale 1ns / 1ps
module tb_motor_ctrl;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [31:0] duty_word = 32'd0;
    reg  [31:0] cfg_word  = 32'd0;
    reg         hb = 1'b0;
    reg         hb_run = 1'b1;
    wire [31:0] ctrl_word = {26'd0, hb, 5'b10101};   // dirA=fwd dirB=fwd enable=1
    wire in1, in2, in3, in4, ena, enb, wd_trip;
    integer a_pm, b_pm, errors;

    motor_ctrl #(.WD_MS(1)) dut (
        .clk(clk), .rst_n(rst_n),
        .duty_word(duty_word), .ctrl_word(ctrl_word), .cfg_word(cfg_word),
        .in1(in1), .in2(in2), .in3(in3), .in4(in4),
        .ena(ena), .enb(enb), .wd_trip(wd_trip));

    always begin
        #200_000;                       // heartbeat toggles every 200 us
        if (hb_run) hb = ~hb;
    end

    task measure;                       // duty over a 2 ms window, in permille
        integer n, ca, cb;
        begin
            ca = 0; cb = 0;
            for (n = 0; n < 200000; n = n + 1) begin
                @(posedge clk);
                ca = ca + ena;
                cb = cb + enb;
            end
            a_pm = ca / 200;
            b_pm = cb / 200;
        end
    endtask

    initial begin
        errors = 0;
        #100 rst_n = 1'b1;

        // 1) pass-through (min_duty = 0)
        duty_word = {16'd750, 16'd250};
        #1_000_000;
        measure;
        $display("[1] min_duty=0   : A=%0d B=%0d permille (expect 250 / 750)", a_pm, b_pm);
        if (a_pm < 248 || a_pm > 252 || b_pm < 748 || b_pm > 752) begin errors = errors + 1; $display("FAIL 1"); end
        if ({in1, in2, in3, in4} !== 4'b0101) begin errors = errors + 1; $display("FAIL direction pins"); end

        // 2) dead-band compensation: 700 + r*300/1000
        cfg_word = 32'd700;
        #500_000;
        measure;
        $display("[2] min_duty=700 : A=%0d B=%0d permille (expect 775 / 925)", a_pm, b_pm);
        if (a_pm < 772 || a_pm > 778 || b_pm < 922 || b_pm > 928) begin errors = errors + 1; $display("FAIL 2"); end

        // 3) zero request stays zero even with dead-band compensation
        duty_word = {16'd750, 16'd0};
        #500_000;
        measure;
        $display("[3] A request 0  : A=%0d B=%0d permille (expect 0 / 925)", a_pm, b_pm);
        if (a_pm != 0 || b_pm < 922 || b_pm > 928) begin errors = errors + 1; $display("FAIL 3"); end

        // 4) watchdog
        hb_run = 1'b0;
        #3_000_000;
        $display("[4] no heartbeat : wd_trip=%b ena=%b enb=%b in=%b%b%b%b (expect 1 1 1 1111)",
                 wd_trip, ena, enb, in1, in2, in3, in4);
        if (wd_trip !== 1'b1 || ena !== 1'b1 || enb !== 1'b1 || {in1, in2, in3, in4} !== 4'b1111) begin
            errors = errors + 1; $display("FAIL 4");
        end

        if (errors == 0) $display("=== tb_motor_ctrl: ALL PASS ===");
        else             $display("=== tb_motor_ctrl: %0d FAILED ===", errors);
        $finish;
    end
endmodule
