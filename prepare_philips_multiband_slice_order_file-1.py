import argparse

def prepare_philips_multiband_slice_order_file(n_slices, multi_band):
    """
    Prepare Philips MultiBand Slice Order File.

    This function generates a list of slice order indices for a Philips MultiBand
    acquisition sequence, based on the provided number of slices and the
    MultiBand acceleration factor.

    Args:
        n_slices (int): Number of slices in the acquisition.
        multi_band (int): MultiBand acceleration factor.

    Returns:
        list: A list of integers representing the slice order indices.

    Raises:
        ValueError: If `n_slices` or `multi_band` is not a valid integer.
        ValueError: If `n_slices` is not a positive integer.
        ValueError: If `multi_band` is not greater than 1.

    Notes:
        - The generated slice order indices are intended for sequences utilizing
          Philips MultiBand acceleration.
        - The returned list represents the order in which the slices are
          acquired.

    Examples:
        result = prepare_philips_multiband_slice_order_file(60, 4)

    Written by: Aleksij Kraljič, Ljubljana, August 18, 2023
    """

    try:
        N = int(n_slices) // int(multi_band)
    except ValueError:
        print("Error: Both number_of_slices and multiband_factor must be integers.")
        sys.exit(1)

    if N <= 0:
        print("Error: Number of slices per multiband group should be a positive integer.")
        sys.exit(1)

    lst = list(range(1, N + 1))

    result = []
    if N % 4 == 0:
        for x in lst:
            if x <= N/2:
                if x % 2 == 0:
                    result.append((x+N)/2)
                else:
                    result.append((x+1)/2)
            else:
                if x % 2 == 0:
                    result.append(N/2-(x-(N/2+2))/2)
                else:
                    result.append(N-1/2-(x-(N/2+2))/2)
    elif N % 2 == 0:
        for x in lst:
            if x <= N/2:
                if x % 2 == 0:
                    result.append((x+N)/2+1)
                else:
                    result.append((x+1)/2)
            else:
                if x % 2 == 0:
                    result.append(N/2-(x-(N/2+2))/2+1/2)
                else:
                    result.append(N-(x-(N/2+2))/2)
    else:
        for x in lst:
            if x % 2 == 0:
                result.append(x/2+(N+1)/2)
            else:
                result.append((x+1)/2)

    result = [int(x) for x in result]
    result = result * multi_band
    return result

def main():
    """
    Prepare Philips MultiBand Slice Order File.

    This script prepares a slice order file for a Philips MultiBand acquisition
    sequence. It generates a list of slice order indices based on the provided
    arguments.

    Command-line Arguments:
        --number_of_slices (int):
            Number of slices in the acquisition.

        --multiband_factor (int):
            MultiBand acceleration factor.

        --output_file_name (str):
            Output file name to save the slice order indices.

    Notes:
        - The generated slice order indices are intended for sequences utilizing
          Philips MultiBand acceleration.
        - The slice order indices are printed to the specified output file.

    Examples:
        To generate a slice order file for 60 slices with a MultiBand factor of 4:
        $ python prepare_philips_multiband_slice_order_file.py \
              --number_of_slices 60 \
              --multiband_factor 4 \
              --output_file_name slice_timing.txt
    """

    parser = argparse.ArgumentParser(epilog=main.__doc__.split("Examples:")[1])
    parser.add_argument("--number_of_slices", type=int, help="Number of slices")
    parser.add_argument("--multiband_factor", type=int, help="MultiBand acceleration factor")
    parser.add_argument("--output_file_name", help="Output file name")
    args = parser.parse_args()

    n_slices = args.number_of_slices
    multiband_factor = args.multiband_factor
    output_file_name = args.output_file_name

    if n_slices < 1:
        print("Error: The number_of_slices should be a positive integer.")
        exit(1)

    if multiband_factor <= 1:
        print("Error: The multiband_factor should be larger than 1. This function is only valid for sequences utilizing Philips MultiBand acceleration.")
        exit(1)
    
    result = prepare_philips_multiband_slice_order_file(n_slices, multiband_factor)
    
    with open(output_file_name, 'w') as f:
        for item in result:
            f.write("%s\n" % item)
    
    print(f"Result written to {output_file_name}")

if __name__ == "__main__":
    main()
