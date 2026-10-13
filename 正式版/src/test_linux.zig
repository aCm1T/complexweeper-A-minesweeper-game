const std = @import("std");
pub fn main() !void {
    var out = std.ArrayList(u8).init(std.heap.page_allocator);
    defer out.deinit();
    const failures = @import("selftest.zig").run(&out);
    try std.io.getStdOut().writeAll(out.items);
    if (failures != 0) std.process.exit(1);
}
