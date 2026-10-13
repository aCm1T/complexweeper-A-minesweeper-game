//! Small, checked C ABI around the original platform-independent game engine.
//! GTK owns presentation; all board generation and rule decisions stay in Zig.
const std = @import("std");
const g = @import("game.zig");

pub const Info = extern struct {
    w: u32, h: u32, mines: u32, mode: u32,
    seed: u32, started: u32, over: u32, win: u32,
    boom: i32, elapsed_ms: u32, moves: u32, msg: u32,
    totals: [4]u32, flags: [4]u32,
};
pub const Cell = extern struct { clue: i16, mine: u8, open: u8, flag: u8, blank: u8 };

export fn cs_create() ?*g.Game {
    const p = std.heap.page_allocator.create(g.Game) catch return null;
    p.* = .{};
    p.newGame(1);
    return p;
}
export fn cs_destroy(p: *g.Game) void { std.heap.page_allocator.destroy(p); }
export fn cs_configure(p: *g.Game, width: u32, height: u32, mines: u32,
    mode: u32, counts: [*]const u32, seed: u32) u32 {
    if (width < 9 or width > g.MAX_W or height < 9 or height > g.MAX_H or mode > 1) return 0;
    const max_mines = width * height - 9;
    var total: u64 = 0;
    for (0..4) |i| total += counts[i];
    if (total > max_mines or (total == 0 and (mines < 1 or mines > max_mines))) return 0;
    p.w = @intCast(width);
    p.h = @intCast(height);
    p.mines = @intCast(if (total > 0) total else mines);
    p.mode = @enumFromInt(mode);
    p.type_count = .{ 0, @intCast(counts[0]), @intCast(counts[1]), @intCast(counts[2]), @intCast(counts[3]) };
    p.newGame(seed);
    return 1;
}
export fn cs_new(p: *g.Game, seed: u32) void { p.newGame(seed); }
export fn cs_tick(p: *g.Game, now_ms: u32) void {
    if (p.started and !p.over) p.elapsed_ms = now_ms -% p.t0;
}
export fn cs_reveal(p: *g.Game, cell: u32, now_ms: u32) u32 {
    if (cell >= p.n or p.over or p.open[cell] != 0 or p.flag[cell] != 0) return 0;
    cs_tick(p, now_ms);
    if (!p.started) {
        p.startAt(cell, now_ms);
        p.setMsg(.started);
        p.checkWin(); // A dense custom board can already finish on its first click.
    } else p.reveal(cell, now_ms);
    return 1;
}
export fn cs_flag(p: *g.Game, cell: u32) u32 {
    if (cell >= p.n) return 0;
    return @intFromBool(p.cycleFlag(cell));
}
export fn cs_expand(p: *g.Game, cell: u32, now_ms: u32) u32 {
    if (cell >= p.n or p.over or p.open[cell] == 0 or p.mine[cell] != 0) return 0;
    cs_tick(p, now_ms);
    p.tryExpand(cell);
    return 1;
}
export fn cs_info(p: *const g.Game, out: *Info) void {
    out.* = .{ .w = p.w, .h = p.h, .mines = p.mines, .mode = @intFromEnum(p.mode),
        .seed = p.seed, .started = @intFromBool(p.started), .over = @intFromBool(p.over),
        .win = @intFromBool(p.win), .boom = p.boom, .elapsed_ms = p.elapsed_ms,
        .moves = p.moves, .msg = @intFromEnum(p.msg), .totals = undefined, .flags = undefined };
    for (0..4) |i| { out.totals[i] = p.type_total[i + 1]; out.flags[i] = p.flags_of[i + 1]; }
}
export fn cs_cells(p: *const g.Game, out: [*]Cell, capacity: u32) u32 {
    if (capacity < p.n) return 0;
    for (0..p.n) |i| out[i] = .{ .clue = p.clue[i], .mine = p.mine[i],
        .open = p.open[i], .flag = p.flag[i], .blank = @intFromBool(p.isBlank(i)) };
    return @intCast(p.n);
}
