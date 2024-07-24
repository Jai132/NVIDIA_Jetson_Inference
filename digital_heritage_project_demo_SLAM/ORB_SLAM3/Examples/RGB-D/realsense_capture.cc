#include <librealsense2/rs.hpp> // Include RealSense Cross Platform API
#include <opencv2/opencv.hpp>   // Include OpenCV API
#include <iostream>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <sys/stat.h> // For creating directories
#include <unistd.h>   // For checking directory existence

// Function to get current Unix time in seconds
std::string getCurrentUnixTime() {
    auto now = std::chrono::system_clock::now();
    auto duration = now.time_since_epoch();
    auto microseconds = std::chrono::duration_cast<std::chrono::microseconds>(duration);
    return std::to_string(microseconds.count());
}

// Function to convert depth frame to a viewable format
cv::Mat convertDepthFrame(const rs2::depth_frame& depth_frame) {
    // Get depth frame dimensions
    int width = depth_frame.get_width();
    int height = depth_frame.get_height();

    // Create OpenCV matrix for the depth frame
    cv::Mat depth_image(cv::Size(width, height), CV_16UC1, (void*)depth_frame.get_data(), cv::Mat::AUTO_STEP);

    // Normalize the depth image to fall within the range 0-255
    cv::Mat depth_image_normalized;
    cv::normalize(depth_image, depth_image_normalized, 0, 255, cv::NORM_MINMAX, CV_8UC1);

    return depth_image_normalized;
}

// Function to check if a directory exists
bool directoryExists(const std::string& dirName) {
    struct stat info;
    if (stat(dirName.c_str(), &info) != 0) {
        return false; // Directory does not exist
    } else if (info.st_mode & S_IFDIR) {
        return true; // Directory exists
    } else {
        return false; // Not a directory
    }
}

// Function to create a directory if it doesn't exist
void createDirectoryIfNotExists(const std::string& dirName) {
    if (!directoryExists(dirName)) {
        mkdir(dirName.c_str(), 0755);
    }
}

int main() {
    try {
        // Create directories if they don't exist
        createDirectoryIfNotExists("../Datasets/custom_rgbd/rgb");
        createDirectoryIfNotExists("../Datasets/custom_rgbd/depth");

        // Declare RealSense pipeline, encapsulating the actual device and sensors
        rs2::pipeline pipe;

        // Create a configuration for the pipeline
        rs2::config cfg;

        // Enable the streams we are interested in
        cfg.enable_stream(RS2_STREAM_COLOR, 640, 480, RS2_FORMAT_BGR8, 60);
        cfg.enable_stream(RS2_STREAM_DEPTH, 640, 480, RS2_FORMAT_Z16, 60);

        // Start the pipeline with the configuration
        rs2::pipeline_profile profile = pipe.start(cfg);

        // Align depth to color stream
        rs2::align align_to_color(RS2_STREAM_COLOR);

        std::cout << "RealSense camera connected and started successfully." << std::endl;

        bool stop = false;

        while (!stop) {
            // Wait for the next set of frames from the camera
            rs2::frameset frames = pipe.wait_for_frames();

            // Align the depth frame to color frame
            frames = align_to_color.process(frames);

            // Get a frame from each stream
            rs2::frame color_frame = frames.get_color_frame();
            rs2::depth_frame depth_frame = frames.get_depth_frame();

            // Create OpenCV matrices from the frames
            cv::Mat color(cv::Size(640, 480), CV_8UC3, (void*)color_frame.get_data(), cv::Mat::AUTO_STEP);
            cv::Mat depth = convertDepthFrame(depth_frame);

            // Generate Unix time filename
            std::string timestamp = getCurrentUnixTime();

            // Save the images in respective directories
            cv::imwrite("../Datasets/custom_rgbd/rgb/" + timestamp + "_color.png", color);
            cv::imwrite("../Datasets/custom_rgbd/depth/" + timestamp + "_depth.png", depth);

            std::cout << "Saved color and depth frames with timestamp: " << timestamp << std::endl;

            // Check for stop condition (Press 'q' to stop)
            if (cv::waitKey(1) == 'q') {
                stop = true;
            }
        }

        // Stop the pipeline
        pipe.stop();
    } catch (const rs2::error &e) {
        std::cerr << "RealSense error calling " << e.get_failed_function() << "(" << e.get_failed_args() << "):\n"
                  << e.what() << std::endl;
        return EXIT_FAILURE;
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
