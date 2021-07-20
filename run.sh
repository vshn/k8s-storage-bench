#!/bin/sh

kubectl apply -f deploy/rbac.yaml
kubectl apply -f deploy/pvc.yaml
kubectl create -f deploy/job.yaml
