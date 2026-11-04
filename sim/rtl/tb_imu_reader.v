`timescale 1ns / 1ps
// ---------------------------------------------------------------------------
// Behavioural MPU6050 I2C slave (address 0x68), just enough for imu_reader.
// ---------------------------------------------------------------------------
module mpu_model (inout sda, input scl);
    reg [7:0] mem [0:255];
    reg       low, active, mode, rw, m_ack;
    reg [1:0] stage;
    reg [3:0] n;
    reg [7:0] rxb, txb, ptr;
    integer   i;
    assign sda = low ? 1'b0 : 1'bz;

    initial begin
        for (i = 0; i < 256; i = i + 1) mem[i] = 8'h00;
        mem[8'h75] = 8'h68;                                   // WHO_AM_I
        mem[8'h3B] = 8'h01; mem[8'h3C] = 8'h23;               // ax = 0x0123
        mem[8'h3D] = 8'h04; mem[8'h3E] = 8'h56;               // ay = 0x0456
        mem[8'h3F] = 8'h40; mem[8'h40] = 8'h00;               // az = 0x4000
        mem[8'h41] = 8'h0A; mem[8'h42] = 8'hBC;               // temp
        mem[8'h43] = 8'h00; mem[8'h44] = 8'h11;               // gx = 0x0011
        mem[8'h45] = 8'hFF; mem[8'h46] = 8'hEE;               // gy = 0xFFEE
        mem[8'h47] = 8'h00; mem[8'h48] = 8'h64;               // gz = 100
        low = 1'b0; active = 1'b0; mode = 1'b0; rw = 1'b0; m_ack = 1'b0;
        stage = 2'd0; n = 4'd0; rxb = 8'd0; txb = 8'd0; ptr = 8'd0;
    end

    always @(negedge sda) if (scl === 1'b1) begin            // START
        active <= 1'b1; mode <= 1'b0; stage <= 2'd0; n <= 4'd0; low <= 1'b0;
    end
    always @(posedge sda) if (scl === 1'b1) begin            // STOP
        active <= 1'b0; mode <= 1'b0; n <= 4'd0; low <= 1'b0;
    end

    always @(posedge scl) if (active) begin
        if (!mode) begin
            if (n < 4'd8) rxb <= {rxb[6:0], sda};
        end else begin
            if (n == 4'd8) m_ack <= ~sda;
        end
        if (n < 4'd9) n <= n + 4'd1;
    end

    always @(negedge scl) if (active) begin
        if (!mode) begin
            if (n == 4'd8) begin
                if (stage == 2'd0) begin
                    if (rxb[7:1] == 7'h68) begin low <= 1'b1; rw <= rxb[0]; end
                    else begin low <= 1'b0; active <= 1'b0; end
                end else if (stage == 2'd1) begin
                    ptr <= rxb; low <= 1'b1;
                end else begin
                    mem[ptr] <= rxb; ptr <= ptr + 8'd1; low <= 1'b1;
                end
            end else if (n == 4'd9) begin
                low <= 1'b0; n <= 4'd0;
                if (stage == 2'd0) begin
                    if (rw) begin
                        mode <= 1'b1; txb <= mem[ptr]; ptr <= ptr + 8'd1; low <= ~mem[ptr][7];
                    end else stage <= 2'd1;
                end else if (stage == 2'd1) stage <= 2'd2;
            end
        end else begin
            if (n >= 4'd1 && n <= 4'd7) low <= ~txb[7 - n];
            else if (n == 4'd8) low <= 1'b0;
            else if (n == 4'd9) begin
                if (m_ack) begin
                    n <= 4'd0; txb <= mem[ptr]; ptr <= ptr + 8'd1; low <= ~mem[ptr][7];
                end else begin
                    mode <= 1'b0; active <= 1'b0; low <= 1'b0;
                end
            end
        end
    end
endmodule

// ---------------------------------------------------------------------------
module tb_imu_reader;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [31:0] cfg_word = 32'd0;
    tri1        scl, sda;
    wire [31:0] ts_w, stat_w, yaw_w, raw_w, now_w;
    integer     errors;
    integer     s0, s1, y0, y1, t0, t1;

    imu_reader #(.PWRUP_US(300), .CAL_SHIFT(3), .AUTO_CAL_AT(5), .SAMPLE_US(1000)) dut (
        .clk(clk), .rst_n(rst_n), .cfg_word(cfg_word), .scl(scl), .sda(sda),
        .ts_word(ts_w), .stat_word(stat_w), .yaw_word(yaw_w), .raw_word(raw_w), .now_word(now_w));
    mpu_model slave (.sda(sda), .scl(scl));

    wire [15:0] seq_w = stat_w[31:16];

    task wait_seq;
        input integer n;
        integer target;
        begin
            target = seq_w + n;
            while (seq_w < target) @(stat_w);
        end
    endtask

    task check_raw;
        input [2:0]  sel;
        input [31:0] expect_v;
        begin
            cfg_word[14:12] = sel;
            #1000;
            if (raw_w !== expect_v) begin
                errors = errors + 1;
                $display("FAIL raw_sel=%0d got %h expect %h", sel, raw_w, expect_v);
            end else $display("ok   raw_sel=%0d = %h", sel, raw_w);
        end
    endtask

    initial begin
        #300_000_000;
        $display("TIMEOUT"); $finish;
    end

    initial begin
        errors = 0;
        #100 rst_n = 1'b1;

        wait (stat_w[1] === 1'b1);
        $display("[1] WHO_AM_I ok, init_done=%b at %0t ns", stat_w[0], $time);
        if (slave.mem[8'h6B] !== 8'h01 || slave.mem[8'h1A] !== 8'h03 ||
            slave.mem[8'h19] !== 8'h00 || slave.mem[8'h1B] !== 8'h00 || slave.mem[8'h1C] !== 8'h00) begin
            errors = errors + 1; $display("FAIL init register writes");
        end else $display("ok   init register writes (6B=01 1A=03 19=00 1B=00 1C=00)");

        wait (stat_w[3] === 1'b1);
        $display("[2] auto calibration done, seq=%0d", seq_w);
        check_raw(3'd0, 32'h0123_0456);
        check_raw(3'd1, 32'h4000_0ABC);
        check_raw(3'd2, 32'h0011_FFEE);
        check_raw(3'd3, 32'h0064_0064);          // {gz, bias}
        check_raw(3'd4, 32'h0000_0068);          // WHO_AM_I

        wait_seq(3);
        if ($signed(yaw_w) < -3 || $signed(yaw_w) > 3) begin
            errors = errors + 1; $display("FAIL yaw should be ~0 at rest, got %0d", $signed(yaw_w));
        end else $display("ok   yaw at rest = %0d mdeg", $signed(yaw_w));

        // spin at +10 deg/s (gz = 1410, bias = 100 -> 1310 LSB / 131 = 10 dps)
        slave.mem[8'h47] = 8'h05; slave.mem[8'h48] = 8'h82;
        wait_seq(3);
        s0 = seq_w; y0 = $signed(yaw_w); t0 = ts_w;
        wait_seq(20);
        s1 = seq_w; y1 = $signed(yaw_w); t1 = ts_w;
        $display("[3] spin: %0d samples, yaw %0d -> %0d mdeg (expect 10 mdeg/sample), ts step %0d us",
                 s1 - s0, y0, y1, t1 - t0);
        if ((y1 - y0) < 10 * (s1 - s0) - 3 || (y1 - y0) > 10 * (s1 - s0) + 3) begin
            errors = errors + 1; $display("FAIL yaw integration");
        end
        if ((t1 - t0) < 1000 * (s1 - s0) - 3 || (t1 - t0) > 1000 * (s1 - s0) + 3) begin
            errors = errors + 1; $display("FAIL timestamp spacing");
        end

        // re-calibrate on request with gz = 300
        slave.mem[8'h47] = 8'h01; slave.mem[8'h48] = 8'h2C;
        cfg_word[16] = 1'b1;
        wait (stat_w[2] === 1'b1);
        cfg_word[16] = 1'b0;
        wait (stat_w[3] === 1'b1);
        wait_seq(12);
        check_raw(3'd3, 32'h012C_012C);
        if ($signed(yaw_w) < -3 || $signed(yaw_w) > 3) begin
            errors = errors + 1; $display("FAIL yaw after re-calibration, got %0d", $signed(yaw_w));
        end else $display("ok   re-calibrated, yaw = %0d mdeg", $signed(yaw_w));

        if (stat_w[15:8] !== 8'd0) begin
            errors = errors + 1; $display("FAIL miss counter = %0d", stat_w[15:8]);
        end
        if (errors == 0) $display("=== tb_imu_reader: ALL PASS ===");
        else             $display("=== tb_imu_reader: %0d FAILED ===", errors);
        $finish;
    end
endmodule
