# MyEnergi Python

## What this is

A poorly-written Python library for [MyEnergi](https://myenergi.com/)'s platform. Their API is not public, so may change and break this library at any time. At the moment it only supports the [Zappi](https://myenergi.com/product/zappi/), and only some of the Zappi functionality. You'll need the [Hub](https://myenergi.com/product/hub/) to make use of it if you don't have one.

There is also support for [Home Assistant](https://www.home-assistant.io/) through a [custom component](https://developers.home-assistant.io/docs/en/creating_component_loading.html).

## What this is not

* Supported
* Production-ready
* Approved by MyEnergi
* Tested particulary well
* A comprehensive API wrapper
* Properly async

## Usage

You'll need to know Python and figure it out. I may get around to improving this documentation one day.

## How?

MyEnergi's mobile apps are developed in React Native, and as such, are fairly easy to reverse engineer. There is no local interface to the MyEnergi Hub, so all information has to be retrieved from the APIs via the internet.

I also found [this community-created documentation](https://github.com/twonk/MyEnergi-App-Api/) after starting my own work.
