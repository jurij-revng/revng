#!/usr/bin/env python3

import sys
from llvmcpy import llvm


def main():
    context = llvm.get_global_context()

    # Load and parse the input file
    buffer = llvm.create_memory_buffer_with_contents_of_file(sys.argv[1])
    module = context.parse_ir(buffer)

    # Identify the CSV (global variable) for the register containing the syscall
    # number (r7 for ARM)
    r7 = module.get_named_global("r7")

    # Prepare requirements to build our call to dprintf

    # 1) Identify the dprintf function (prototype)
    dprintf = module.get_named_function("dprintf")

    # 2) Create an integer constant for stderr
    two = context.int32_type().const_int(2, True)

    # 3) Create the message to print
    message_str = context.const_string("%d\n", 4, True)
    message = module.add_global(message_str.type_of(), "message")
    message.set_initializer(message_str)
    message_ptr = message.const_bit_cast(context.int8_type().pointer(0))

    # Identify the function generated by revng (root)
    root_function = module.get_named_function("root")

    # Loop over all the generated instructions and add instrumentation code
    builder = context.create_builder()
    for basic_block in root_function.iter_basic_blocks():
        for instruction in basic_block.iter_instructions():
            # Check if the current instruction is a call
            if instruction.instruction_opcode == llvm.Call:
                # The callee is the last operand
                last_operand_index = instruction.get_num_operands() - 1
                callee = instruction.get_operand(last_operand_index)

                # If there's a bitcast, skip it
                if not callee.name:
                    assert callee.get_num_operands() == 1
                    callee = callee.get_operand(0)

                # Check if it's performing a syscall
                if callee.name.startswith("helper_exception_with_syndrome_"):
                    # Set the builder's insert point before the call instruction
                    builder.position_builder_before(instruction)

                    # Load the value of r7 (which contains the syscall number)
                    load_r7 = builder.build_load(r7, "")

                    # Create the list of arguments for dprintf
                    arguments = [two, message_ptr, load_r7]

                    # Create the function call to dprintf:
                    # dprintf(2, "%d\n", r7)
                    builder.build_call(dprintf, arguments, "")

    # Produce the instrumented LLVM IR to file
    module.print_module_to_file(sys.argv[2])


if __name__ == "__main__":
    main()
