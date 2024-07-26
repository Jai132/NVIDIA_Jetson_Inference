#include <librealsense2/rs.hpp> // Include RealSense Cross Platform API
#include <opencv2/opencv.hpp>   // Include OpenCV API
#include <iostream>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <sys/stat.h> // For creating directories
#include <unistd.h>   // For checking directory existence
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <fstream>    // For file operations

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
    // Assuming Kinect measures in mm, and realsense in meters.
    cv::Mat depth_image(cv::Size(width, height), CV_16UC1, (void*)depth_frame.get_data(), cv::Mat::AUTO_STEP);
    depth_image = depth_image * 1000.0f; // Convert to mm

    // // TODO: REMOVE: Normalize the depth image to fall within the range 0-255
    // cv::Mat depth_image_normalized;
    // cv::normalize(depth_image, depth_image_normalized, 0, 255, cv::NORM_MINMAX, CV_8UC1);

    return depth_image;//depth_image_normalized;//
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

// Frame buffer to hold frames
std::queue<rs2::frameset> frameBuffer;
std::mutex bufferMutex;
std::condition_variable bufferCondVar;
bool stopProcessing = false;

// Frame processing function
void processFrames(std::ofstream& rgbFile, std::ofstream& depthFile) {
    while (true) {
        std::unique_lock<std::mutex> lock(bufferMutex);
        bufferCondVar.wait(lock, [] { return !frameBuffer.empty() || stopProcessing; });

        if (stopProcessing && frameBuffer.empty()) {
            break;
        }

        rs2::frameset frames = frameBuffer.front();
        frameBuffer.pop();
        lock.unlock();

        // Align the depth frame to color frame
        rs2::align align_to_color(RS2_STREAM_COLOR);
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
        std::string colorFileName = "rgb/" + timestamp + ".png";
        std::string depthFileName = "depth/" + timestamp + ".png";
        cv::imwrite("../Datasets/custom_rgbd/rgb/" + timestamp + ".png", color);
        cv::imwrite("../Datasets/custom_rgbd/depth/" + timestamp + ".png", depth);

        // Write the timestamps and file paths to the text files
        rgbFile << timestamp << " " << colorFileName << std::endl;
        depthFile << timestamp << " " << depthFileName << std::endl;

        std::cout << "Saved color and depth frames with timestamp: " << timestamp << std::endl;
    }
}

int main() {
    try {
        // Create directories if they don't exist
        createDirectoryIfNotExists("../Datasets/custom_rgbd/rgb");
        createDirectoryIfNotExists("../Datasets/custom_rgbd/depth");

        // Open text files for writing timestamps and paths
        std::ofstream rgbFile("../Datasets/custom_rgbd/rgb.txt");
        std::ofstream depthFile("../Datasets/custom_rgbd/depth.txt");

        if (!rgbFile.is_open() || !depthFile.is_open()) {
            std::cerr << "Failed to open output files." << std::endl;
            return EXIT_FAILURE;
        }

        // Declare RealSense pipeline, encapsulating the actual device and sensors
        rs2::pipeline pipe;

        // Create a configuration for the pipeline
        rs2::config cfg;

        // Enable the streams we are interested in
        cfg.enable_stream(RS2_STREAM_COLOR, 640, 480, RS2_FORMAT_BGR8, 60);
        cfg.enable_stream(RS2_STREAM_DEPTH, 640, 480, RS2_FORMAT_Z16, 60);

        // Start the pipeline with the configuration
        rs2::pipeline_profile profile = pipe.start(cfg);

        std::cout << "RealSense camera connected and started successfully." << std::endl;

        // Start frame processing thread
        std::thread processingThread(processFrames, std::ref(rgbFile), std::ref(depthFile));

        bool stop = false;

        while (!stop) {
            // Wait for the next set of frames from the camera
            rs2::frameset frames = pipe.wait_for_frames();

            // Add frames to buffer
            std::unique_lock<std::mutex> lock(bufferMutex);
            frameBuffer.push(frames);
            lock.unlock();
            bufferCondVar.notify_one();

            // Check for stop condition (Press 'q' to stop)
            if (cv::waitKey(1) == 'q') {
                stop = true;
                std::unique_lock<std::mutex> lock(bufferMutex);
                stopProcessing = true;
                bufferCondVar.notify_all();
            }
        }

        // Stop the pipeline
        pipe.stop();

        // Wait for processing thread to finish
        processingThread.join();

        // Close the text files
        rgbFile.close();
        depthFile.close();
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
