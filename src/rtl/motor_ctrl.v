`timescale 1ns / 1ps
// motor_ctrl v2  --  dual-channel PWM / direction / watchdog for an L298N
//   duty_word [15:0]=A, [31:16]=B  requested duty 0..1000 (permille)
//   ctrl_word [1:0]=dirA [3:2]=dirB [4]=enable [5]=heartbeat (toggle it faster than WD_MS)
//             dir: 00 coast, 01 forward, 10 reverse, 11 brake
//   cfg_word  [9:0]=min_duty : dead-band compensation.  request r (1..1000) is mapped to
//             min_duty + r*(1000-min_duty)/1000 ; r = 0 stays 0.  min_duty = 0 -> pass-through.
module motor_ctrl #(
    parameter integer CLK_HZ    = 100_000_000,
    parameter integer PWM_DIV   = 10,      // 10 kHz
    parameter integer PWM_STEPS = 1000,
    parameter integer WD_MS     = 200
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] duty_word,
    input  wire [31:0] ctrl_word,
    input  wire [31:0] cfg_word,
    output reg         in1, in2, in3, in4,
    output reg         ena, enb,
    output wire        wd_trip
);
    localparam integer WD_CYCLES = (CLK_HZ / 1000) * WD_MS;
    localparam [15:0]  STEPS16   = PWM_STEPS;

    // ---------------- PWM time base
    reg [7:0]  div_cnt;
    reg [15:0] pwm_cnt;
    wire tick = (div_cnt == PWM_DIV - 1);
    wire wrap = tick && (pwm_cnt == PWM_STEPS - 1);
    always @(posedge clk) begin
        if (!rst_n) begin
            div_cnt <= 8'd0; pwm_cnt <= 16'd0;
        end else if (tick) begin
            div_cnt <= 8'd0;
            pwm_cnt <= (pwm_cnt == PWM_STEPS - 1) ? 16'd0 : pwm_cnt + 16'd1;
        end else begin
            div_cnt <= div_cnt + 8'd1;
        end
    end

    // ---------------- dead-band compensation (pipelined, DSP-friendly)
    wire [15:0] da_in  = (duty_word[15:0]  > STEPS16) ? STEPS16 : duty_word[15:0];
    wire [15:0] db_in  = (duty_word[31:16] > STEPS16) ? STEPS16 : duty_word[31:16];
    wire [15:0] min_d  = (cfg_word[9:0] > STEPS16) ? STEPS16 : {6'd0, cfg_word[9:0]};
    wire [15:0] span   = STEPS16 - min_d;
    reg  [31:0] pa, pb;
    reg  [15:0] ea, eb;
    wire [47:0] ma = pa * 48'd1049;        // x/1000 ~= x*1049 >> 20
    wire [47:0] mb = pb * 48'd1049;
    always @(posedge clk) begin
        pa <= da_in * span;
        pb <= db_in * span;
        ea <= (da_in == 16'd0) ? 16'd0 : (min_d + ma[35:20]);
        eb <= (db_in == 16'd0) ? 16'd0 : (min_d + mb[35:20]);
    end

    // duty registers update only at the end of a PWM period (glitch-free)
    reg [15:0] da, db;
    always @(posedge clk) begin
        if (!rst_n) begin
            da <= 16'd0; db <= 16'd0;
        end else if (wrap) begin
            da <= ea; db <= eb;
        end
    end
    wire pwm_a = (pwm_cnt < da);
    wire pwm_b = (pwm_cnt < db);

    // ---------------- hardware watchdog: heartbeat bit must toggle
    reg        hb_d;
    reg [31:0] wd_cnt;
    reg        tripped;
    always @(posedge clk) begin
        if (!rst_n) begin
            hb_d <= ctrl_word[5]; wd_cnt <= 32'd0; tripped <= 1'b1;
        end else begin
            hb_d <= ctrl_word[5];
            if (ctrl_word[5] != hb_d) begin
                wd_cnt <= 32'd0; tripped <= 1'b0;
            end else if (wd_cnt >= WD_CYCLES) begin
                tripped <= 1'b1;
            end else begin
                wd_cnt <= wd_cnt + 32'd1;
            end
        end
    end
    assign wd_trip = tripped;

    // ---------------- outputs (brake when inactive)
    wire       active = ctrl_word[4] & ~tripped;
    wire [1:0] dir_a  = ctrl_word[1:0];
    wire [1:0] dir_b  = ctrl_word[3:2];
    always @(posedge clk) begin
        if (!rst_n || !active) begin
            in1 <= 1'b1; in2 <= 1'b1; in3 <= 1'b1; in4 <= 1'b1;
            ena <= 1'b1; enb <= 1'b1;
        end else begin
            in1 <= dir_a[1]; in2 <= dir_a[0];
            in3 <= dir_b[1]; in4 <= dir_b[0];
            ena <= (dir_a == 2'b11) ? 1'b1 : pwm_a;
            enb <= (dir_b == 2'b11) ? 1'b1 : pwm_b;
        end
    end
endmodule
